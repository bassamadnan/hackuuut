import os
import json
from typing import Dict, List, Optional, Any
from langchain_openai import AzureChatOpenAI
from langchain.schema import HumanMessage, AIMessage
from langchain.memory import ConversationBufferMemory

# Memory store for conversations
memory_store = {}

def load_agents(file_path="agents.json"):
    """Load agents data from file."""
    with open(file_path, "r") as f:
        return json.load(f)["agents"]

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

def format_tools_context(agent):
    """Format existing tools for prompt context."""
    tools_context = "Existing tools:\n"
    for tool in agent["tools"]:
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

def generate_tool(query, agent_id, session_id=None, agents_data=None):
    """Generate a tool based on query and agent."""
    # Load agents if not provided
    if agents_data is None:
        agents_data = load_agents()
    
    # Create a session ID if not provided
    session_id = session_id or f"session_{len(memory_store) + 1}"
    
    # Get memory
    memory = get_memory(session_id)
    
    # Find the selected agent
    agent = next((a for a in agents_data if a["id"] == agent_id), None)
    if not agent:
        return {"error": f"Agent with ID {agent_id} not found"}
    
    # Get LLM
    llm = get_llm()
    
    # Format context
    tools_context = format_tools_context(agent)
    history_text = format_history(memory)
    
    # Create prompt
    prompt = f"""
You are a tool generation assistant that creates Python functions and BaseTool definitions.

QUERY: {query}
AGENT: {agent["name"]} - {agent["description"]}
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
    
    # Store the generated tool in memory
    memory.chat_memory.add_ai_message(tool_code)
    
    return {
        "code": tool_code,
        "agent": agent["name"],
        "session_id": session_id
    }

def process_feedback(feedback, session_id, agent_id, query=None, agents_data=None):
    """Process feedback and regenerate tool."""
    # Load agents if not provided
    if agents_data is None:
        agents_data = load_agents()
    
    # Check if session exists
    if session_id not in memory_store:
        return {"error": "Session not found"}
    
    # Find the selected agent
    agent = next((a for a in agents_data if a["id"] == agent_id), None)
    if not agent:
        return {"error": f"Agent with ID {agent_id} not found"}
    
    # Get memory
    memory = get_memory(session_id)
    
    # Add feedback to memory
    memory.chat_memory.add_user_message(feedback)
    
    # Get LLM
    llm = get_llm()
    
    # Format context
    tools_context = format_tools_context(agent)
    original_query = query or find_original_query(memory)
    history_text = format_history(memory)
    
    # Create prompt
    prompt = f"""
You are a tool generation assistant that creates Python functions and BaseTool definitions.

QUERY: {original_query}
AGENT: {agent["name"]} - {agent["description"]}
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
    
    # Store the regenerated tool in memory
    memory.chat_memory.add_ai_message(tool_code)
    
    return {
        "code": tool_code,
        "agent": agent["name"],
        "session_id": session_id
    }

def approve_tool(agent_id, code, session_id=None):
    """Save an approved tool (placeholder)."""
    # Here you would save the tool to your database or file
    print(f"Tool approved and added to toolkit for agent {agent_id}")
    
    # Optionally clear session memory
    if session_id and session_id in memory_store:
        del memory_store[session_id]
    
    return {"success": True, "message": f"Tool added to toolkit for agent {agent_id}"}

def get_agents_list(agents_data=None):
    """Get list of available agents."""
    if agents_data is None:
        agents_data = load_agents()
    
    return [{"id": agent["id"], "name": agent["name"], "description": agent["description"]} 
            for agent in agents_data]


# Usage:
# import os
# from new_func import generate_tool, process_feedback, approve_tool

# # Set environment variables
# os.environ["AZURE_OPENAI_ENDPOINT"] = "your-endpoint"
# os.environ["AZURE_OPENAI_API_KEY"] = "your-key"
# os.environ["AZURE_OPENAI_DEPLOYMENT"] = "your-deployment"

# # Generate a tool
# result = generate_tool(
#     query="Create a tool to list all S3 buckets",
#     agent_id="aws-agent"
# )

# # Get generated code
# code = result["code"]
# session_id = result["session_id"]

# # Process feedback (if needed)
# improved = process_feedback(
#     feedback="Add support for region parameter",
#     session_id=session_id,
#     agent_id="aws-agent"
# )

# # Approve the final tool
# approve_tool(
#     agent_id="aws-agent",
#     code=improved["code"],
#     session_id=improved["session_id"]
# )