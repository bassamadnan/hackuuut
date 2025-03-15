import os
from langchain_openai import AzureChatOpenAI
from langchain.schema import HumanMessage

def generate_tool(query, agent_description="", existing_tools=None):
    """
    Generate a tool function and BaseTool definition using Azure OpenAI.
    
    Args:
        query: The user query requiring a new tool
        agent_description: Description of the agent that will use this tool
        existing_tools: List of dicts with name and description of existing tools
        
    Returns:
        str: Python code for the function and BaseTool definition
    """
    # Initialize Azure OpenAI client
    llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        temperature=0.2
    )
    
    # Format existing tools context
    existing_tools_context = ""
    if existing_tools:
        existing_tools_context = "Existing tools:\n"
        for tool in existing_tools:
            existing_tools_context += f"- {tool['name']}: {tool['description']}\n"
    
    # Create prompt directly
    prompt = f"""
You are a tool generation assistant that creates Python functions and BaseTool definitions.

QUERY: {query}
AGENT: {agent_description}
{existing_tools_context}

Generate ONLY a Python function and its corresponding BaseTool definition to address this query.
The function should have proper type hints, docstrings, and implementation.
The BaseTool should have a name, description, parameters, and required fields.

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
    
    # Use direct message approach
    message = HumanMessage(content=prompt)
    
    # Get response
    response = llm.invoke([message])
    tool_code = response.content
    
    # Clean up markdown
    if "```python" in tool_code:
        tool_code = tool_code.split("```python")[1]
    elif "```" in tool_code:
        tool_code = tool_code.split("```")[0]
    
    return tool_code.strip()

# Example usage
if __name__ == "__main__":
    query = "delete an EC2 instance with given instance ID"
    agent_description = "AWS cloud management agent"
    existing_tools = [
        {"name": "list_ec2_instances_tool", "description": "Lists all EC2 instances in a region"}
    ]
    
    tool_code = generate_tool(query, agent_description, existing_tools)
    print(tool_code)