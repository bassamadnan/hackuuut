"""Tool generator for Moya framework"""
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
You are a tool generation assistant that creates Python functions and BaseTool definitions for the Moya framework.

QUERY: {query}
AGENT: {agent_name} - {agent_description}
{tools_context}
{history_text}

Generate a Python function and its corresponding BaseTool definition to address this query.
DO NOT use type hints from the typing module unless you include the proper import.
DO NOT use Dict, List, Optional, or Any directly without importing them.
Keep the function simple and avoid unnecessary imports.
The BaseTool should have a name, description, parameters, and required fields.
Make the tool generic, not specific to any particular instance or situation.

Use the following format:
```python
def function_name(param1, param2):
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
    
    print(
        {
        "code": tool_code,
        "agent_name": agent_name,
        "session_id": session_id,
        "function_name": function_name
    }
    )
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
    original_query = query
    history_text = format_history(memory)
    print("passing tools_context ", tools_context , "\n" , "original query:", original_query, "\n", "history text: ", history_text)
    # Create prompt
    prompt = f"""
You are a tool generation assistant that creates Python functions and BaseTool definitions for the Moya framework.

QUERY: {original_query}
AGENT: {agent_name} - {agent_description}
{tools_context}
{history_text}

LATEST FEEDBACK: {feedback}

Generate a Python function and its corresponding BaseTool definition to address this query.
DO NOT use type hints from the typing module unless you include the proper import.
DO NOT use Dict, List, Optional, or Any directly without importing them.
Keep the function simple and avoid unnecessary imports.
The BaseTool should have a name, description, parameters, and required fields.
Make the tool generic, not specific to any particular instance or situation.

Use the following format:
```python
def function_name(param1, param2):
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
    print(
        {
        "code": tool_code,
        "agent_name": agent_name,
        "session_id": session_id,
        "function_name": function_name
    }
    )
    return {
        "code": tool_code,
        "agent_name": agent_name,
        "session_id": session_id,
        "function_name": function_name
    }