import os
import json
import re
from typing import Dict, List, Optional, Any
from langchain_openai import AzureChatOpenAI
from langchain.schema import HumanMessage, AIMessage
from langchain.memory import ConversationBufferMemory

# Memory store for conversations
memory_store = {}

def get_memory(session_id):
    """Get or create memory for a session."""
    if session_id not in memory_store:
        memory_store[session_id] = ConversationBufferMemory()
    return memory_store[session_id]

def get_llm():
    """Initialize and return LLM."""
    return AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        temperature=0.2
    )

def format_tools_context(tools):
    """Format existing tools for prompt context."""
    tools_context = "Existing tools:\n"
    for tool in tools:
        tools_context += f"- {tool['name']}: {tool['description']}\n"
    return tools_context

def format_history(memory):
    """Format conversation history for prompt context."""
    history = memory.chat_memory.messages if hasattr(memory, "chat_memory") else []
    
    history_text = ""
    if history:
        history_text = "\nPrevious iterations:\n"
        for msg in history:
            if isinstance(msg, HumanMessage):
                if msg.content.startswith("QUERY:"):
                    history_text += f"User request: {msg.content.split('QUERY:')[1].strip()}\n"
                else:
                    history_text += f"User feedback: {msg.content}\n"
            elif isinstance(msg, AIMessage):
                history_text += f"Generated tool: {msg.content}\n"
    
    return history_text

def find_original_query(memory):
    """Extract original query from memory."""
    history = memory.chat_memory.messages if hasattr(memory, "chat_memory") else []
    
    for msg in history:
        if isinstance(msg, HumanMessage) and msg.content.startswith("QUERY:"):
            return msg.content.split("QUERY:")[1].strip()
    
    return ""

def clean_code(code):
    """Clean up markdown code blocks."""
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0]
    elif "```" in code:
        code = code.split("```")[1].split("```")[0]
    
    return code.strip()

def extract_function_name(code):
    """Extract the function name from the generated code."""
    # Find the first function definition
    match = re.search(r"def\s+([a-zA-Z0-9_]+)\s*\(", code)
    if match:
        return match.group(1)
    
    # Try to find tool name
    match = re.search(r"([a-zA-Z0-9_]+)_tool\s*=\s*BaseTool", code)
    if match:
        return match.group(1)
    
    return None

def generate_tool(query, agent_name, agent_description, tools, session_id=None):
    """Generate a tool based on query and agent info."""
    # Create a session ID if not provided
    session_id = session_id or f"session_{len(memory_store) + 1}"
    
    # Get memory
    memory = get_memory(session_id)
    
    # Get LLM
    llm = get_llm()
    
    # Format context
    tools_context = format_tools_context(tools)
    history_text = format_history(memory)
    
    # Create prompt
    prompt = f"""
You are a tool generation assistant that creates Python functions and BaseTool definitions.

QUERY: {query}
AGENT: {agent_name} - {agent_description}
{tools_context}
{history_text}

Generate a Python function and its corresponding BaseTool definition to address this query.
Include necessary imports at the top of the code (e.g., boto3 for AWS, csv for data processing).
The function should have proper type hints, docstrings, and implementation.
The BaseTool should have a name, description, parameters, and required fields.
Make the tool generic, not specific to any particular instance or situation.

Use the following format:
```python
# Include necessary imports here
import boto3  # if dealing with AWS
import json   # if handling JSON data
import csv    # if working with CSV files
# Add any other imports needed

def function_name(param1: type, param2: type) -> return_type:
    \"\"\"
    Description of what the function does.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
    \"\"\"
    # Function implementation
    
function_name_tool = BaseTool(
    name="function_name_tool",
    description="Description of the tool",
    function=function_name,
    parameters={{
        "param1": {{
            "type": "string",
            "description": "Description of param1"
        }},
        "param2": {{
            "type": "string", 
            "description": "Description of param2"
        }}
    }},
    required=["param1", "param2"]
)
```
"""
    
    # Store the user query in memory
    memory.chat_memory.add_user_message(f"QUERY: {query}")
    
    # Get response from LLM
    message = HumanMessage(content=prompt)
    response = llm.invoke([message])
    tool_code = response.content
    
    # Clean up code
    tool_code = clean_code(tool_code)
    
    # Extract function name
    function_name = extract_function_name(tool_code)
    
    # Store the generated tool in memory
    memory.chat_memory.add_ai_message(tool_code)
    
    return {
        "code": tool_code,
        "agent_name": agent_name,
        "session_id": session_id,
        "function_name": function_name
    }

def process_feedback(feedback, session_id, agent_name, agent_description, tools, query=None):
    """Process feedback and regenerate tool."""
    # Check if session exists
    if session_id not in memory_store:
        return {"error": "Session not found"}
    
    # Get memory
    memory = get_memory(session_id)
    
    # Add feedback to memory
    memory.chat_memory.add_user_message(feedback)
    
    # Get LLM
    llm = get_llm()
    
    # Format context
    tools_context = format_tools_context(tools)
    original_query = query or find_original_query(memory)
    history_text = format_history(memory)
    
    # Create prompt
    prompt = f"""
You are a tool generation assistant that creates Python functions and BaseTool definitions.

QUERY: {original_query}
AGENT: {agent_name} - {agent_description}
{tools_context}
{history_text}

LATEST FEEDBACK: {feedback}

Generate a Python function and its corresponding BaseTool definition to address this query.
Include necessary imports at the top of the code (e.g., boto3 for AWS, csv for data processing).
The function should have proper type hints, docstrings, and implementation.
The BaseTool should have a name, description, parameters, and required fields.
Make the tool generic, not specific to any particular instance or situation.

Use the following format:
```python
# Include necessary imports here
import boto3  # if dealing with AWS
import json   # if handling JSON data
import csv    # if working with CSV files
# Add any other imports needed

def function_name(param1: type, param2: type) -> return_type:
    \"\"\"
    Description of what the function does.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
    \"\"\"
    # Function implementation
    
function_name_tool = BaseTool(
    name="function_name_tool",
    description="Description of the tool",
    function=function_name,
    parameters={{
        "param1": {{
            "type": "string",
            "description": "Description of param1"
        }},
        "param2": {{
            "type": "string", 
            "description": "Description of param2"
        }}
    }},
    required=["param1", "param2"]
)
```
"""
    
    # Get response from LLM
    message = HumanMessage(content=prompt)
    response = llm.invoke([message])
    tool_code = response.content
    
    # Clean up code
    tool_code = clean_code(tool_code)
    
    # Extract function name
    function_name = extract_function_name(tool_code)
    
    # Store the regenerated tool in memory
    memory.chat_memory.add_ai_message(tool_code)
    
    return {
        "code": tool_code,
        "agent_name": agent_name,
        "session_id": session_id,
        "function_name": function_name
    }

def approve_tool(agent_name, code, function_name, session_id=None):
    """Save an approved tool (placeholder)."""
    # Here you would save the tool to your database or file
    print(f"Tool '{function_name}' approved and added to toolkit for agent '{agent_name}'")
    
    # Optionally clear session memory
    if session_id and session_id in memory_store:
        del memory_store[session_id]
    
    return {
        "success": True, 
        "message": f"Tool '{function_name}' added to toolkit for agent '{agent_name}'",
        "function_name": function_name
    }

# Example agent info
agent_name = "AWS Cloud Manager"
agent_description = "Agent for managing AWS cloud resources and infrastructure"
tools = [
    {
        "name": "list_ec2_instances_tool",
        "description": "Lists all EC2 instances in a specified region"
    },
    {
        "name": "start_ec2_instance_tool",
        "description": "Starts an EC2 instance with the given instance ID"
    }
]

# # Generate a tool
# result = generate_tool(
#     query="Create a tool to delete an S3 bucket",
#     agent_name=agent_name,
#     agent_description=agent_description,
#     tools=tools
# )

# # Access the function name
# function_name = result["function_name"]
# code = result["code"]
# session_id = result["session_id"]

# # Process feedback
# improved = process_feedback(
#     feedback="Add error handling for bucket not found",
#     session_id=session_id,
#     agent_name=agent_name,
#     agent_description=agent_description,
#     tools=tools
# )

# # Approve the tool
# approval = approve_tool(
#     agent_name=agent_name,
#     code=improved["code"],
#     function_name=improved["function_name"],
#     session_id=improved["session_id"]
# )