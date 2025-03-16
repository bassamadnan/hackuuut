from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import re
from typing import Dict, List, Optional, Any
from langchain_openai import AzureChatOpenAI
from langchain.schema import HumanMessage, AIMessage
from langchain.memory import ConversationBufferMemory
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Memory store for conversations
memory_store = {}

class ToolRequest(BaseModel):
    query: str
    agent_name: str
    agent_description: str
    tools: List[Dict[str, str]]
    session_id: Optional[str] = None

class FeedbackRequest(BaseModel):
    session_id: str
    feedback: str
    agent_name: str
    agent_description: str
    tools: List[Dict[str, str]]
    query: Optional[str] = None

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

@app.post("/generate-tool")
async def generate_tool_endpoint(request: ToolRequest = Body(...)):
    """Generate a tool based on query and agent info."""
    try:
        result = generate_tool(
            query=request.query,
            agent_name=request.agent_name,
            agent_description=request.agent_description,
            tools=request.tools,
            session_id=request.session_id
        )
        return result
    except Exception as e:
        return {"error": str(e)}

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

@app.post("/feedback")
async def feedback_endpoint(request: FeedbackRequest = Body(...)):
    """Process feedback and regenerate tool."""
    try:
        result = process_feedback(
            feedback=request.feedback,
            session_id=request.session_id,
            agent_name=request.agent_name,
            agent_description=request.agent_description,
            tools=request.tools,
            query=request.query
        )
        return result
    except Exception as e:
        return {"error": str(e)}

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

@app.post("/approve-tool")
async def approve_endpoint(data: Dict = Body(...)):
    """Approves a tool."""
    try:
        print(data.get("function_name"))
        result = approve_tool(
            agent_name=data.get("agent_name"),
            code=data.get("code"),
            function_name=data.get("function_name"),
            session_id=data.get("session_id")
        )
        return result
    except Exception as e:
        return {"error": str(e)}

def approve_tool(agent_name, code, function_name, session_id=None):
    """Save an approved tool (placeholder)."""
    # Here you would save the tool to your database or file
    print(f"Tool '{function_name}' approved and added to toolkit for agent '{agent_name}'")
    
    # Optionally clear session memory
    if session_id and session_id in memory_store:
        del memory_store[session_id]
    print(function_name)
    return {
        "success": True, 
        "message": f"Tool '{function_name}' added to toolkit for agent '{agent_name}'",
        "function_name": function_name
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)