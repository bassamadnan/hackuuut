import os
import uuid
import time
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv

# Import components from dynamic tool generation setup
from moya.conversation.thread import Thread
from moya.tools.base_tool import BaseTool
from moya.tools.ephemeral_memory import EphemeralMemory
from moya.tools.tool_registry import ToolRegistry
from moya.registry.agent_registry import AgentRegistry
from moya.orchestrators.multi_agent_orchestrator_concurrent import MultiAgentOrchestratorConcurrent
from moya.agents.azure_openai_agent import AzureOpenAIAgent, AzureOpenAIAgentConfig
from moya.conversation.message import Message
from moya.classifiers.llm_classifier_concurrent import LLMClassifierConcurrent
from new_func import generate_tool

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("dynamic-agent-backend")

# Initialize FastAPI
app = FastAPI(title="Dynamic Multi-Agent System API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class AgentRequest(BaseModel):
    message: str

class AgentResponse(BaseModel):
    session_id: str
    status: str

class StatusResponse(BaseModel):
    status: str
    messages: List[Dict[str, Any]]
    iterations: int

# In-memory storage for sessions
sessions = {}

# Import tool functions from existing codebase
from paste import (
    list_s3_buckets,
    describe_ec2_instance,
    search_logs,
    get_error_count
)

# Create new dynamic tooling agent class (from the first file)
class AzureOpenAIDynamicToolingAgent(AzureOpenAIAgent):
    def __init__(self, config: AzureOpenAIAgentConfig):
        super().__init__(config=config)
        self.generate_dynamic_tool_tool = BaseTool(
            name="generate_dynamic_tool_tool",
            description="Tool to generate a new tool dynamically and add it to this agent",
            function=self.generate_dynamic_tool_fn,
            parameters={
                "requirement": {
                    "type": "string",
                    "description": "The description of the task to be achieved by the newly created tool"
                }
            },
            required=["requirement"]
        )
        self.tool_registry.register_tool(self.generate_dynamic_tool_tool)
        self.system_prompt += "\nIf none of your current tools can perform the task requested by the user, use the generate_dynamic_tool_tool to create a new tool that can handle the request."

    def generate_dynamic_tool_fn(self, requirement: str):
        """Generate a new tool based on the requirement and add it to the agent."""
        try:
            # Format existing tools for context
            tools = []
            for tool in self.tool_registry.get_tools():
                tool_info = {
                    "name": tool.name,
                    "description": tool.description
                }
                tools.append(tool_info)

            # Generate the tool code
            result = generate_tool(
                query=requirement,
                agent_name=self.agent_name,
                agent_description=self.description,
                tools=tools
            )

            # Get generated code
            code = result["code"]
            function_name = result["function_name"]
            
            # Use locals() dictionary to store the function
            local_vars = {}
            
            # Execute the code in the local scope
            exec(code, globals(), local_vars)
            
            # Extract the tool from the local scope
            tool_name = f"{function_name}_tool"
            if tool_name in local_vars:
                new_tool = local_vars[tool_name]
                self.tool_registry.register_tool(new_tool)
                return f"Successfully created and registered a new tool: {new_tool.name} - {new_tool.description}"
            else:
                return f"Tool was generated but could not find {tool_name} in the execution scope."
                
        except Exception as e:
            logger.error(f"Failed to generate tool: {str(e)}")
            return f"Failed to generate tool: {str(e)}"

def setup_tool_registry():
    """Set up and configure the shared tool registry."""
    tool_registry = ToolRegistry()
    
    # Configure memory tools
    EphemeralMemory.configure_memory_tools(tool_registry)
    
    return tool_registry

def create_aws_agent(tool_registry):
    """Create an AWS specialized agent with dynamic tool generation capability."""
    # Create AWS-specific tools
    list_s3_buckets_tool = BaseTool(
        name="list_s3_buckets_tool",
        description="Tool to list all S3 buckets in the AWS account",
        function=list_s3_buckets,
        parameters={},
        required=[]
    )
    
    describe_ec2_instance_tool = BaseTool(
        name="describe_ec2_instance_tool",
        description="Tool to describe an EC2 instance by its ID",
        function=describe_ec2_instance,
        parameters={
            "instance_id": {
                "type": "string",
                "description": "The ID of the EC2 instance to describe"
            }
        },
        required=["instance_id"]
    )
    
    # Create a registry copy for this agent
    aws_tool_registry = ToolRegistry()
    
    # Add memory tools
    for tool in tool_registry.get_tools():
        aws_tool_registry.register_tool(tool)
    
    # Add AWS-specific tools
    aws_tool_registry.register_tool(list_s3_buckets_tool)
    aws_tool_registry.register_tool(describe_ec2_instance_tool)
    
    # Create agent configuration
    agent_config = AzureOpenAIAgentConfig(
        agent_name="aws_agent",
        agent_type="ChatAgent",
        description="Agent specialized in AWS cloud operations",
        system_prompt="""You are an AWS cloud specialist agent.
        You can help with AWS-related operations and provide information about AWS resources.
        You have access to tools that can list S3 buckets and describe EC2 instances.
        If you don't have a tool for a specific AWS operation, you can generate a new tool.
        Be helpful, concise, and professional in your responses.""",
        tool_registry=aws_tool_registry,
        model_name="gpt-4o",
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION") or "2024-12-01-preview"
    )
    
    # Create and return the dynamic tooling agent
    return AzureOpenAIDynamicToolingAgent(config=agent_config)

def create_logging_agent(tool_registry):
    """Create a Logging specialized agent with dynamic tool generation capability."""
    # Create logging-specific tools
    search_logs_tool = BaseTool(
        name="search_logs_tool",
        description="Tool to search logs with a specific query and log level",
        function=search_logs,
        parameters={
            "query": {
                "type": "string",
                "description": "The search query"
            },
            "log_level": {
                "type": "string",
                "description": "The log level to filter by (info, error, warn, debug, all)"
            }
        },
        required=["query"]
    )
    
    get_error_count_tool = BaseTool(
        name="get_error_count_tool",
        description="Tool to get count of error logs in a specified timeframe",
        function=get_error_count,
        parameters={
            "timeframe": {
                "type": "string",
                "description": "The timeframe to count errors (last_hour, last_day, last_week)"
            }
        },
        required=[]
    )
    
    # Create a registry copy for this agent
    logging_tool_registry = ToolRegistry()
    
    # Add memory tools
    for tool in tool_registry.get_tools():
        logging_tool_registry.register_tool(tool)
    
    # Add logging-specific tools
    logging_tool_registry.register_tool(search_logs_tool)
    logging_tool_registry.register_tool(get_error_count_tool)
    
    # Create agent configuration
    agent_config = AzureOpenAIAgentConfig(
        agent_name="logging_agent",
        agent_type="ChatAgent",
        description="Agent specialized in log analysis and monitoring",
        system_prompt="""You are a log analysis and monitoring specialist agent.
        You can help search logs, analyze error patterns, and monitor system health.
        You have access to tools that can search logs and get error counts.
        If you don't have a tool for a specific logging operation, you can generate a new tool.
        Be helpful, analytical, and focused in your responses.""",
        tool_registry=logging_tool_registry,
        model_name="gpt-4o",
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION") or "2024-12-01-preview"
    )
    
    # Create and return the dynamic tooling agent
    return AzureOpenAIDynamicToolingAgent(config=agent_config)

def create_classifier_agent(tool_registry):
    """Create a classifier agent to route messages to the appropriate agent."""
    # Create agent configuration
    agent_config = AzureOpenAIAgentConfig(
        agent_name="classifier",
        agent_type="AgentClassifier",
        description="Classifier for routing messages to specialized agents",
        system_prompt="""You are a classifier. Your job is to determine the best agent based on the user's message:
        1. If the message asks about AWS services, cloud resources, S3, EC2, or any AWS-related operations, return 'aws_agent'
        2. If the message asks about logs, monitoring, errors, system health, or mentions log analysis, return 'logging_agent'
        3. For any other query, determine the closest match based on the query content
        
        Analyze the intent of the message carefully.
        Return only the agent name as specified above.""",
        tool_registry=tool_registry,
        model_name="gpt-4o",
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION") or "2024-12-01-preview"
    )
    
    # Create and return the classifier agent
    return AzureOpenAIAgent(config=agent_config)

def setup_orchestrator():
    """Set up the multi-agent orchestrator with all components."""
    # Set up shared tool registry
    shared_tool_registry = setup_tool_registry()
    
    # Create specialized agents with dynamic tool generation
    aws_agent = create_aws_agent(shared_tool_registry)
    logging_agent = create_logging_agent(shared_tool_registry)
    
    # Create classifier agent
    classifier_agent = create_classifier_agent(shared_tool_registry)
    
    # Set up agent registry
    registry = AgentRegistry()
    registry.register_agent(aws_agent)
    registry.register_agent(logging_agent)
    
    logger.info("=== REGISTERED AGENTS ===")
    logger.info("AWS Agent and Logging Agent have been registered")
    logger.info("=========================")
    
    # Create and configure the classifier
    classifier = LLMClassifierConcurrent(classifier_agent, default_agent="aws_agent")
    
    # Create the orchestrator
    orchestrator = MultiAgentOrchestratorConcurrent(
        agent_registry=registry,
        classifier=classifier,
        default_agent_name="aws_agent"
    )
    
    return orchestrator

# Setup orchestrator globally
global_orchestrator = setup_orchestrator()

class MessageHandler:
    """Class to handle message processing and collection for web API"""
    def __init__(self, thread_id):
        self.thread_id = thread_id
        self.messages = []
        self.iterations = 0
        self.current_iteration = 1
        
    def append_message(self, agent, content):
        """Add a message to the collection"""
        message_id = f"{agent}-{len(self.messages) + 1}"
        timestamp = datetime.now().isoformat()
        
        message = {
            "id": message_id,
            "role": "assistant",
            "agent": agent,
            "content": content,
            "timestamp": timestamp,
            "iteration": self.current_iteration
        }
        
        self.messages.append(message)
        return message
    
    def increment_iteration(self):
        """Signal completion of an iteration"""
        self.iterations = self.current_iteration
        self.current_iteration += 1
        # Add a marker for the frontend to identify iteration boundaries
        self.messages.append({
            "type": "iteration",
            "iteration": self.iterations
        })
        # Add a marker for the frontend to identify iteration boundaries
        self.messages.append({
            "type": "iteration",
            "iteration": self.iterations
        })

async def process_agent_request(thread_id: str, user_message: str):
    """Process an agent request asynchronously"""
    logger.info(f"Starting agent processing with thread_id {thread_id}")
    
    # Initialize session data
    sessions[thread_id] = {
        "status": "running",
        "messages": [],
        "iterations": 0,
        "handler": MessageHandler(thread_id)
    }
    
    handler = sessions[thread_id]["handler"]
    
    # Store initial system message
    EphemeralMemory.store_message(
        thread_id=thread_id,
        sender="system",
        content="Starting conversation with multi-agent system capable of dynamic tool generation."
    )
    
    # Store the user message
    EphemeralMemory.store_message(thread_id=thread_id, sender="user", content=user_message)
    
    # Get conversation history if it exists
    session_summary = EphemeralMemory.get_thread_summary(thread_id)
    enriched_input = f"{session_summary}\nCurrent user message: {user_message}"
    
    # First, add classifier decision
    try:
        # Determine which agent to use
        # selected_agent = global_orchestrator.classifier.classify(user_message)

        
        # Add classifier message
        classifier_message = handler.append_message(
            "classifier",
            f"I'll help with your request by analyzing AWS costs. I'll coordinate with specialized agents to investigate this issue thoroughly."
        )
        
        # Simulate a short delay for classifier processing
        await asyncio.sleep(1)
        
        def stream_callback(chunk):
            # Skip - we'll collect the final response
            pass
        
        response = global_orchestrator.orchestrate(
            thread_id=thread_id,
            user_message=enriched_input,
            stream_callback=stream_callback
        )
        
     
        
        # Complete first iteration
        handler.increment_iteration()
        
        # Store the assistant's response
        EphemeralMemory.store_message(thread_id=thread_id, sender="assistant", content=response)
        
        # Simulate a follow-up analysis if needed
        if "NEXT_STEP" in response or "CONTINUE" in response:
            # Classifier decides to do a second iteration
            await asyncio.sleep(2)
            
            classifier_decision = handler.append_message(
                "classifier",
                "Based on initial findings, we need to examine this further. I'll initiate a deeper analysis."
            )
            
            # Deep analysis prompt
            follow_up_message = f"{session_summary}\nBased on the initial findings, please provide a more detailed analysis."
            
            # Second iteration of agent processing
            response2 = global_orchestrator.orchestrate(
                thread_id=thread_id,
                user_message=follow_up_message,
                stream_callback=stream_callback
            )
            

            
            # Complete second iteration
            handler.increment_iteration()
            
            # Store the follow-up response
            EphemeralMemory.store_message(thread_id=thread_id, sender="assistant", content=response2)
            
            # If there's a final recommendation phase needed
            if "NEXT_STEP" in response2 or "CONTINUE" in response2:
                await asyncio.sleep(2)
                
                classifier_final = handler.append_message(
                    "classifier",
                    "Now that we understand the situation, let's finalize with specific recommendations."
                )
                
                # Final recommendations prompt
                final_message = f"{session_summary}\nBased on our analysis, please provide concrete recommendations and next steps."
                
                # Third iteration
                response3 = global_orchestrator.orchestrate(
                    thread_id=thread_id,
                    user_message=final_message,
                    stream_callback=stream_callback
                )

                
                # Complete third iteration
                handler.increment_iteration()
                
                # Store the final response
                EphemeralMemory.store_message(thread_id=thread_id, sender="assistant", content=response3)
                
                # Add a summary message from the classifier
                summary = handler.append_message(
                    "classifier",
                    "I've completed my analysis with multiple iterations. The recommendations above provide a comprehensive action plan based on our findings."
                )
        
        # Update session status
        sessions[thread_id]["status"] = "complete"
        sessions[thread_id]["messages"] = handler.messages
        sessions[thread_id]["iterations"] = handler.iterations
        
        logger.info(f"Agent processing completed for thread_id {thread_id} with {handler.iterations} iterations")
    
    except Exception as e:
        logger.error(f"Error in agent processing: {str(e)}")
        sessions[thread_id]["status"] = "error"
        sessions[thread_id]["messages"].append({
            "id": "error-1",
            "role": "system",
            "agent": "system",
            "content": f"Error processing request: {str(e)}",
            "timestamp": datetime.now().isoformat(),
            "iteration": 1
        })

# API Endpoints
@app.get("/")
async def root():
    return {"message": "Dynamic Multi-Agent System API is running"}

@app.post("/api/agent_demo/start", response_model=AgentResponse)
async def start_agent(request: AgentRequest, background_tasks: BackgroundTasks):
    thread_id = str(uuid.uuid4())
    background_tasks.add_task(process_agent_request, thread_id, request.message)
    return {"session_id": thread_id, "status": "started"}

@app.get("/api/agent_demo/status", response_model=StatusResponse)
async def get_status(thread_id: str):
    if thread_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[thread_id]
    return {
        "status": session["status"],
        "messages": session["messages"],
        "iterations": session["iterations"]
    }

# Main entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=True)