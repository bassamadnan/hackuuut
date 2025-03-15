from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import os
import json
from langchain_openai import AzureChatOpenAI
from langchain.schema import HumanMessage, AIMessage
from langchain.memory import ConversationBufferMemory
from pydantic import BaseModel
from typing import List, Dict, Optional, Any

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load agents data
with open("agents.json", "r") as f:
    AGENTS_DATA = json.load(f)["agents"]

# Memory store for conversations
memory_store = {}

class Tool(BaseModel):
    name: str
    description: str
    parameters: Optional[Dict] = None

class ToolRequest(BaseModel):
    query: str
    agent_id: str
    session_id: Optional[str] = None

class FeedbackRequest(BaseModel):
    session_id: str
    feedback: str
    agent_id: str
    query: Optional[str] = None

@app.get("/agents")
async def get_agents():
    """Get all available agents."""
    return {"agents": [{"id": agent["id"], "name": agent["name"], "description": agent["description"]} 
                     for agent in AGENTS_DATA]}

@app.post("/generate-tool")
async def generate_tool(request: ToolRequest = Body(...)):
    """Generate a tool function based on query and selected agent."""
    try:
        # Create a session ID if not provided
        session_id = request.session_id or f"session_{len(memory_store) + 1}"
        
        # Initialize memory for this session if it doesn't exist
        if session_id not in memory_store:
            memory_store[session_id] = ConversationBufferMemory()
        
        # Find the selected agent
        agent = next((a for a in AGENTS_DATA if a["id"] == request.agent_id), None)
        if not agent:
            return {"error": f"Agent with ID {request.agent_id} not found"}
        
        llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            temperature=0.2
        )
        
        # Format existing tools context
        existing_tools_context = "Existing tools:\n"
        for tool in agent["tools"]:
            existing_tools_context += f"- {tool['name']}: {tool['description']}\n"
        
        # Get conversation history
        memory = memory_store[session_id]
        history = memory.chat_memory.messages if hasattr(memory, "chat_memory") else []
        
        # Format history for prompt
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
        
        # Create prompt
        prompt = f"""
You are a tool generation assistant that creates Python functions and BaseTool definitions.

QUERY: {request.query}
AGENT: {agent["name"]} - {agent["description"]}
{existing_tools_context}
{history_text}

Generate ONLY a Python function and its corresponding BaseTool definition to address this query.
The function should have proper type hints, docstrings, and implementation.
The BaseTool should have a name, description, parameters, and required fields.
Make the tool generic, not specific to any particular instance or situation.

Use the following format:
```python
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

DO NOT include any imports, explanations, or any text outside the function and BaseTool definition.
"""
        
        # Store the user query in memory
        memory.chat_memory.add_user_message(f"QUERY: {request.query}")
        
        # Get response from LLM
        message = HumanMessage(content=prompt)
        response = llm.invoke([message])
        tool_code = response.content
        
        # Clean up markdown
        if "```python" in tool_code:
            tool_code = tool_code.split("```python")[1].split("```")[0]
        elif "```" in tool_code:
            tool_code = tool_code.split("```")[1].split("```")[0]
        
        # Store the generated tool in memory
        memory.chat_memory.add_ai_message(tool_code.strip())
        
        return {
            "code": tool_code.strip(), 
            "agent": agent["name"],
            "session_id": session_id
        }
    
    except Exception as e:
        return {"error": str(e)}

@app.post("/feedback")
async def process_feedback(request: FeedbackRequest = Body(...)):
    """Process feedback and regenerate tool."""
    try:
        if request.session_id not in memory_store:
            return {"error": "Session not found"}
        
        # Find the selected agent
        agent = next((a for a in AGENTS_DATA if a["id"] == request.agent_id), None)
        if not agent:
            return {"error": f"Agent with ID {request.agent_id} not found"}
        
        # Get memory for this session
        memory = memory_store[request.session_id]
        
        # Add feedback to memory
        memory.chat_memory.add_user_message(request.feedback)
        
        llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            temperature=0.2
        )
        
        # Format existing tools context
        existing_tools_context = "Existing tools:\n"
        for tool in agent["tools"]:
            existing_tools_context += f"- {tool['name']}: {tool['description']}\n"
        
        # Get conversation history
        history = memory.chat_memory.messages if hasattr(memory, "chat_memory") else []
        
        # Find the original query
        original_query = ""
        for msg in history:
            if isinstance(msg, HumanMessage) and msg.content.startswith("QUERY:"):
                original_query = msg.content.split("QUERY:")[1].strip()
                break
        
        # Format history for prompt
        history_text = "\nPrevious iterations:\n"
        for msg in history:
            if isinstance(msg, HumanMessage):
                if msg.content.startswith("QUERY:"):
                    history_text += f"User request: {msg.content.split('QUERY:')[1].strip()}\n"
                else:
                    history_text += f"User feedback: {msg.content}\n"
            elif isinstance(msg, AIMessage):
                history_text += f"Generated tool: {msg.content}\n"
        
        # Create prompt
        prompt = f"""
You are a tool generation assistant that creates Python functions and BaseTool definitions.

QUERY: {request.query}
AGENT: {agent["name"]} - {agent["description"]}
{existing_tools_context}
{history_text}

Generate a Python function and its corresponding BaseTool definition to address this query.
Include necessary imports at the top of the code (e.g., boto3 for AWS, csv for data processing).
The function should have proper type hints, docstrings, and implementation.
The BaseTool should have a name, description, parameters, and required fields.
Make the tool generic, not specific to any particular instance or situation.

Use the following format:
```python
# Include ONLY necessary imports here for eg:
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
        
        # Clean up markdown
        if "```python" in tool_code:
            tool_code = tool_code.split("```python")[1].split("```")[0]
        elif "```" in tool_code:
            tool_code = tool_code.split("```")[1].split("```")[0]
        
        # Store the regenerated tool in memory
        memory.chat_memory.add_ai_message(tool_code.strip())
        
        return {
            "code": tool_code.strip(), 
            "agent": agent["name"],
            "session_id": request.session_id
        }
    
    except Exception as e:
        return {"error": str(e)}

@app.post("/approve-tool")
async def approve_tool(data: Dict = Body(...)):
    """Approves a tool (placeholder)."""
    agent_id = data.get("agent_id")
    code = data.get("code")
    session_id = data.get("session_id")
    
    print(f"Tool approved and added to toolkit for agent {agent_id}")
    # Here you would save the tool to your database or file
    
    # Optionally clear session memory
    if session_id and session_id in memory_store:
        del memory_store[session_id]
    
    return {"success": True, "message": f"Tool added to toolkit for agent {agent_id}"}

if __name__ == "__main__":
    import uvicorn
    
    # Check if agents.json exists, if not create it
    if not os.path.exists("agents.json"):
        with open("agents.json", "w") as f:
            json.dump({"agents": []}, f)
            print("Created empty agents.json file")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)