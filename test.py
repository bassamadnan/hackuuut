"""
Multi-agent system with dynamic tool generation capability, using concurrent orchestration.
"""

import os
import random
import logging
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
import threading
import traceback

# Configure basic logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# For tracking iterations
ITERATION_COUNTERS = {"current": 0}

# Custom orchestrator with better error handling
class SafeMultiAgentOrchestratorConcurrent(MultiAgentOrchestratorConcurrent):
    
    def orchestrate(self, thread_id: str, user_message: str, stream_callback=None, **kwargs) -> str:
        """
        Orchestrate the message handling using intelligent agent selection with improved error handling.

        :param thread_id: The conversation thread ID
        :param user_message: The message from the user
        :param stream_callback: Optional callback for streaming responses
        :param kwargs: Additional context
        :return: The concatenated response from all the chosen agents
        """
        EphemeralMemory.store_message(thread_id=thread_id, sender="user", content=user_message)
        
        all_responses = []
        current_message = user_message
        max_iterations = 5
        available_agents = self.agent_registry.list_agents()
        if not available_agents:
            return "[No agents available to handle message.]"
        
        for _ in range(max_iterations):
            agent_names = self.classifier.classify(
                message=current_message,
                thread_id=thread_id,
                available_agents=available_agents
            )
            
            if not agent_names and self.default_agent_name:
                agent_names = [self.default_agent_name]
            
            agents = [self.agent_registry.get_agent(name) for name in agent_names if name]
            agents = [agent for agent in agents if agent]
            
            if not agents:
                if all_responses:
                    return "\n\n".join(all_responses) + "\n\n[No suitable agent found for next step.]"
                return "[No suitable agent found to handle message.]"
            
            responses = {}
            
            def run_agent(agent):
                agent_prefix = f"[{agent.agent_name}] "
                try:
                    agent_response = agent.handle_message(current_message, thread_id=thread_id, **kwargs)
                    responses[agent.agent_name] = agent_prefix + agent_response
                except Exception as e:
                    error_msg = str(e)
                    tb = traceback.format_exc()
                    logger.error(f"Error in agent {agent.agent_name}: {error_msg}\n{tb}")
                    responses[agent.agent_name] = f"{agent_prefix}Error processing request: {error_msg}"
                    if stream_callback:
                        stream_callback(f"\n{agent_prefix}Error processing request: {error_msg}\n")
            
            threads = []
            for agent in agents:
                thread = threading.Thread(target=run_agent, args=(agent,))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            # Ensure we have at least one response from each agent
            for agent in agents:
                if agent.agent_name not in responses:
                    responses[agent.agent_name] = f"[{agent.agent_name}] Failed to generate a response."
            
            # Print responses for debugging
            if stream_callback:
                for agent_name, response in responses.items():
                    stream_callback(f"\n--- Response from {agent_name} ---\n{response}\n")
            
            current_output = "\n\n".join(responses.values())
            all_responses.append(current_output)
            
            if "STOP" in current_output:
                if stream_callback:
                    stream_callback("\n[Workflow stopped based on agent decision]\n")
                break
            
            if "NEXT_STEP" in current_output or "CONTINUE" in current_output:
                if "NEXT_MESSAGE:" in current_output:
                    parts = current_output.split("NEXT_MESSAGE:")
                    if len(parts) > 1:
                        current_message = parts[1].split("\n")[0].strip()
                    else:
                        current_message = f"Based on these results, what action should be taken?\n{current_output}"
                else:
                    current_message = f"Continue processing based on these results:\n{current_output}"
                
                if stream_callback:
                    stream_callback("\n[Processing next step...]\n")
            else:
                break
        
        final_response = "\n\n".join(all_responses)
        
        EphemeralMemory.store_message(
            thread_id=thread_id, 
            sender="MultiAgentOrchestratorConcurrent", 
            content=final_response
        )
        
        return final_response

# Create new dynamic tooling agent class
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

# ------------------------------------
# Base tool functions for AWS agent
# ------------------------------------

def list_s3_buckets():
    """
    List all S3 buckets in the AWS account.
    
    Returns:
        str: A string listing all S3 buckets.
    """
    try:
        # Mock response
        buckets = ["data-bucket-1", "logs-bucket", "backup-bucket", "app-assets"]
        return f"S3 Buckets: {', '.join(buckets)}"
    except Exception as e:
        logger.error(f"Error listing S3 buckets: {str(e)}")
        return f"Error listing S3 buckets: {str(e)}"

def describe_ec2_instance(instance_id: str = None):
    """
    Describe an EC2 instance by its ID.
    
    Args:
        instance_id (str, optional): The ID of the EC2 instance. If not provided, will list available instances.
        
    Returns:
        str: A string with instance details or a list of available instances.
    """
    try:
        # Mock implementation
        instances = {
            "i-1234567890abcdef0": {
                "InstanceType": "t2.micro",
                "State": "running",
                "LaunchTime": "2023-01-01T00:00:00Z",
                "PrivateIpAddress": "10.0.0.1"
            },
            "i-0987654321fedcba0": {
                "InstanceType": "t2.medium",
                "State": "stopped",
                "LaunchTime": "2023-02-01T00:00:00Z",
                "PrivateIpAddress": "10.0.0.2"
            }
        }
        
        # If no instance_id provided, list available instances
        if not instance_id:
            instance_list = []
            for id, details in instances.items():
                instance_list.append(f"{id}: {details['InstanceType']} ({details['State']})")
            return f"Available EC2 instances:\n" + "\n".join(instance_list)
        
        if instance_id in instances:
            instance = instances[instance_id]
            return f"Instance {instance_id}: Type={instance['InstanceType']}, State={instance['State']}, IP={instance['PrivateIpAddress']}"
        else:
            return f"Instance {instance_id} not found."
    except Exception as e:
        logger.error(f"Error describing EC2 instance: {str(e)}")
        return f"Error describing EC2 instance: {str(e)}"

# ------------------------------------
# Base tool functions for Logging agent
# ------------------------------------

def search_logs(query: str, log_level: str = "all"):
    """
    Search logs with a specific query and log level.
    
    Args:
        query (str): The search query.
        log_level (str): The log level to filter by (info, error, warn, debug, all).
        
    Returns:
        str: A string with matching log entries.
    """
    try:
        # Mock implementation
        mock_logs = [
            {"timestamp": "2023-01-01T12:00:00Z", "level": "ERROR", "message": "Database connection failed", "service": "api"},
            {"timestamp": "2023-01-01T12:05:00Z", "level": "INFO", "message": "User logged in", "service": "auth"},
            {"timestamp": "2023-01-01T12:10:00Z", "level": "WARN", "message": "High CPU usage detected", "service": "monitoring"},
            {"timestamp": "2023-01-01T12:15:00Z", "level": "DEBUG", "message": "Processing user request", "service": "api"},
            {"timestamp": "2023-01-01T12:20:00Z", "level": "ERROR", "message": "Payment processing failed", "service": "payment"}
        ]
        
        # Filter logs
        filtered_logs = []
        for log in mock_logs:
            if (log_level.lower() == "all" or log["level"].lower() == log_level.lower()) and query.lower() in log["message"].lower():
                filtered_logs.append(f"{log['timestamp']} [{log['level']}] {log['service']}: {log['message']}")
        
        if filtered_logs:
            return "Found logs:\n" + "\n".join(filtered_logs)
        else:
            return f"No logs found matching query '{query}' with level '{log_level}'."
    except Exception as e:
        logger.error(f"Error searching logs: {str(e)}")
        return f"Error searching logs: {str(e)}"

def get_error_count(timeframe: str = "last_hour"):
    """
    Get count of error logs in a specified timeframe.
    
    Args:
        timeframe (str): The timeframe to count errors (last_hour, last_day, last_week).
        
    Returns:
        str: A string with error count information.
    """
    try:
        # Mock implementation
        error_counts = {
            "last_hour": {"count": 12, "services": {"api": 5, "auth": 2, "database": 5}},
            "last_day": {"count": 45, "services": {"api": 15, "auth": 8, "database": 22}},
            "last_week": {"count": 156, "services": {"api": 68, "auth": 23, "database": 65}}
        }
        
        if timeframe in error_counts:
            data = error_counts[timeframe]
            services = ", ".join([f"{svc}: {count}" for svc, count in data["services"].items()])
            return f"Errors in {timeframe}: {data['count']} total ({services})"
        else:
            return f"Invalid timeframe. Use 'last_hour', 'last_day', or 'last_week'."
    except Exception as e:
        logger.error(f"Error getting error count: {str(e)}")
        return f"Error getting error count: {str(e)}"

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
        description="Tool to describe an EC2 instance by its ID. If no ID is provided, lists all available instances.",
        function=describe_ec2_instance,
        parameters={
            "instance_id": {
                "type": "string",
                "description": "The ID of the EC2 instance to describe (optional)"
            }
        },
        required=[]  # Make instance_id optional
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
    """Create a classifier agent to route messages to the appropriate agents."""
    # Create agent configuration
    agent_config = AzureOpenAIAgentConfig(
        agent_name="classifier",
        agent_type="AgentClassifier",
        description="Classifier for routing messages to specialized agents",
        system_prompt="""You are a classifier that determines which specialized agents should handle user requests.
        Analyze the user's message and select ALL relevant specialized agents that should process this request concurrently.
        
        Available agents are:
        - aws_agent: Specialized in AWS cloud operations, S3 buckets, EC2 instances, and other AWS resources
        - logging_agent: Specialized in log analysis, monitoring, error patterns, and system health
        
        For each user query, determine ALL agents that would be helpful in providing a comprehensive response.
        For example, a query about AWS logs might need both the aws_agent AND the logging_agent.
        
        Return only agent names separated by commas. For example:
        - "aws_agent,logging_agent" if both are relevant
        - "aws_agent" if only AWS expertise is needed
        - "logging_agent" if only logging expertise is needed""",
        tool_registry=tool_registry,
        model_name="gpt-4o",
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION") or "2024-12-01-preview"
    )
    
    # Create and return the classifier agent
    return AzureOpenAIAgent(config=agent_config)

# Custom wrapper for tracking iterations and formatting responses
class IterationTrackingCallback:
    def __init__(self, original_callback=None):
        self.original_callback = original_callback
        self.buffer = ""
        
    def __call__(self, chunk):
        # Track iteration progress
        if "[Processing next step...]" in chunk:
            ITERATION_COUNTERS["current"] += 1
            print(f"\n[ITERATION {ITERATION_COUNTERS['current']} STARTING...]\n")
            chunk = chunk.replace("[Processing next step...]", "")
        
        # Remove empty lines and clean up formatting
        if chunk.strip():
            # Clean up the chunk and make sure it's properly displayed
            self.buffer += chunk
            
            # Pass to original callback for display
            if self.original_callback:
                self.original_callback(chunk)
            else:
                print(chunk, end="", flush=True)

def setup_orchestrator():
    """Set up the concurrent multi-agent orchestrator with all components."""
    # Reset iteration counter
    ITERATION_COUNTERS["current"] = 0
    
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
    
    # Print simple confirmation
    print("=== REGISTERED AGENTS ===")
    print("AWS Agent and Logging Agent have been registered")
    print("=========================")
    
    # Create and configure the concurrent classifier
    classifier = LLMClassifierConcurrent(classifier_agent, default_agent="aws_agent")
    
    # Create the concurrent orchestrator
    orchestrator = SafeMultiAgentOrchestratorConcurrent(
        agent_registry=registry,
        classifier=classifier,
        default_agent_name="aws_agent"
    )
    
    return orchestrator

def main():
    # Set up the orchestrator with all components
    orchestrator = setup_orchestrator()
    thread_id = "multi_agent_dynamic_tools"
    
    print("=== Multi-Agent System with Dynamic Tool Generation ===")
    print("You can ask about AWS services or log analysis.")
    print("If the agent doesn't have a tool for your request, it can generate one!")
    print("The system now supports CONCURRENT agent responses - multiple agents can work on your request at once!")
    print("Type 'exit' to quit")
    print("-" * 50)
    
    # Store initial system message
    EphemeralMemory.store_message(
        thread_id=thread_id, 
        sender="system", 
        content="Starting conversation with multi-agent system capable of dynamic tool generation and concurrent processing."
    )
    
    while True:
        # Get user input
        user_message = input("\nYou: ").strip()
        
        # Check for exit condition
        if user_message.lower() in ['exit', 'quit']:
            print("\nGoodbye!")
            break
        
        # Store the user message
        EphemeralMemory.store_message(thread_id=thread_id, sender="user", content=user_message)
        
        # Get conversation history
        session_summary = EphemeralMemory.get_thread_summary(thread_id)
        enriched_input = f"{session_summary}\nCurrent user message: {user_message}"
        
        # Print Assistant prompt and get response
        print("\nAssistant: ", end="", flush=True)
        
        try:
            # Create the iteration tracking callback
            stream_callback = IterationTrackingCallback(lambda chunk: print(chunk, end="", flush=True))
            
            # Orchestrate the response with the tracking callback
            response = orchestrator.orchestrate(
                thread_id=thread_id,
                user_message=enriched_input,
                stream_callback=stream_callback
            )
            
            # Only print the completion message (the response content should have been streamed already)
            print(f"\n\n[Completed with {ITERATION_COUNTERS['current']} iterations]")
            print()  # New line after response
        except Exception as e:
            logger.error(f"Error in orchestration: {str(e)}")
            print(f"\nError: {str(e)}")
            response = "I encountered an error processing your request."
        
        # Reset iteration counter for next request
        ITERATION_COUNTERS["current"] = 0
        
        # Store the assistant's response
        EphemeralMemory.store_message(thread_id=thread_id, sender="assistant", content=response)

if __name__ == "__main__":
    main()