"""
Test script for the concurrent multi-agent orchestrator with verbose logging.
"""

import os
import time
import uuid
from dotenv import load_dotenv
from moya.agents.azure_openai_agent import AzureOpenAIAgent, AzureOpenAIAgentConfig
from moya.classifiers.llm_classifier_concurrent import LLMClassifierConcurrent
from moya.orchestrators.multi_agent_orchestrator_concurrent import MultiAgentOrchestratorConcurrent
from moya.registry.agent_registry import AgentRegistry
from moya.tools.ephemeral_memory import EphemeralMemory
from moya.tools.tool_registry import ToolRegistry

# Load environment variables
load_dotenv()

# Enable verbose logging
VERBOSE = True

def log(message, level=0):
    """Print log message with timestamp and indentation."""
    if VERBOSE:
        indent = "  " * level
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        print(f"[{timestamp}] {indent}{message}")

# Create a custom classifier that logs decisions
class VerboseLLMClassifierConcurrent(LLMClassifierConcurrent):
    def classify(self, message, thread_id=None, available_agents=None):
        log("🔍 Classifier starting classification process...")
        log(f"🔍 Available agents: {[agent.name for agent in available_agents]}", 1)
        
        result = super().classify(message, thread_id, available_agents)
        
        log(f"🔍 Classifier selected agents: {result}", 1)
        return result

# Custom wrapper for agent to log all calls
class VerboseAgentWrapper:
    def __init__(self, agent):
        self._agent = agent
        self.agent_name = agent.agent_name
        self.agent_type = agent.agent_type
        self.description = agent.description
        
    def handle_message(self, message, **kwargs):
        log(f"🤖 Agent '{self.agent_name}' processing message...", 1)
        start_time = time.time()
        
        result = self._agent.handle_message(message, **kwargs)
        
        elapsed = time.time() - start_time
        log(f"🤖 Agent '{self.agent_name}' completed in {elapsed:.2f}s", 1)
        log(f"🤖 Response summary: {result[:100]}...(truncated)", 2)
        
        return result
    
    def handle_message_stream(self, message, **kwargs):
        log(f"🤖 Agent '{self.agent_name}' processing message (streaming)...", 1)
        return self._agent.handle_message_stream(message, **kwargs)
    
    def __getattr__(self, name):
        return getattr(self._agent, name)

def setup_test():
    """Set up the test environment with agents and orchestrator."""
    log("📋 Setting up test environment...")
    
    # Set up shared components
    tool_registry = ToolRegistry()
    EphemeralMemory.configure_memory_tools(tool_registry)
    agent_registry = AgentRegistry()
    
    log("📋 Configured memory tools and registries", 1)

    # Create classifier agent
    log("📋 Creating classifier agent...", 1)
    classifier_config = AzureOpenAIAgentConfig(
        agent_name="classifier",
        agent_type="Classifier",
        description="Agent selection classifier",
        model_name="gpt-4o-mini",
        system_prompt="""You are a classifier that determines which specialized agents should handle user requests.
        Analyze the user's message and select ALL relevant specialized agents that should process this request concurrently.
        
        Available agents are:
        - data_analyst: Analyzes data and provides insights
        - programmer: Writes and explains code
        - security_expert: Provides cybersecurity advice
        
        Return ONLY agent names separated by commas. For example: "data_analyst,programmer" 
        or "security_expert" or "data_analyst,programmer,security_expert".
        DO NOT include any other text or explanations.""",
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version="2023-07-01-preview"
    )
    classifier_agent = AzureOpenAIAgent(config=classifier_config)
    log("📋 Classifier agent created", 1)

    # Create specialized agents
    agent_configs = [
        ("data_analyst", "Analyzes data and provides insights", 
         "You specialize in data analysis. Provide detailed statistics and insights about data structures, database optimization, and data visualization."),
        
        ("programmer", "Writes and explains code", 
         "You are a programming expert. Write clean, efficient code and explain technical concepts related to software development and system architecture."),
        
        ("security_expert", "Provides cybersecurity advice", 
         "You are a cybersecurity expert. Identify security risks and provide recommendations for securing data and systems.")
    ]

    log("📋 Creating specialized agents:", 1)
    for name, desc, prompt in agent_configs:
        log(f"📋 Creating agent: {name}", 2)
        config = AzureOpenAIAgentConfig(
            agent_name=name,
            agent_type="Specialist",
            description=desc,
            model_name="gpt-4o-mini",
            system_prompt=prompt,
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version="2023-07-01-preview"
        )
        agent = AzureOpenAIAgent(config=config)
        # Wrap with verbose logging
        wrapped_agent = VerboseAgentWrapper(agent)
        agent_registry.register_agent(wrapped_agent)
        log(f"📋 Agent '{name}' created and registered", 2)

    # Set up the concurrent classifier and orchestrator
    log("📋 Setting up classifier and orchestrator...", 1)
    classifier = VerboseLLMClassifierConcurrent(classifier_agent, default_agent="programmer")
    
    # Override the orchestrator's orchestrate method to add verbose logging
    class VerboseMultiAgentOrchestratorConcurrent(MultiAgentOrchestratorConcurrent):
        def orchestrate(self, thread_id, user_message, stream_callback=None, **kwargs):
            log("🔄 Orchestrator starting process...")
            log(f"🔄 Thread ID: {thread_id}", 1)
            log(f"🔄 Message: {user_message[:100]}...(truncated)", 1)
            
            # Store original message
            EphemeralMemory.store_message(thread_id=thread_id, sender="user", content=user_message)
            log("🔄 User message stored in memory", 1)
            
            result = super().orchestrate(thread_id, user_message, stream_callback, **kwargs)
            
            log("🔄 Orchestration complete", 1)
            return result
    
    orchestrator = VerboseMultiAgentOrchestratorConcurrent(
        agent_registry=agent_registry,
        classifier=classifier,
        default_agent_name="programmer"
    )
    log("📋 Orchestrator created", 1)
    
    return orchestrator

def run_test(orchestrator):
    """Run a test with a complex query that requires multiple agents."""
    thread_id = f"concurrent_test_{uuid.uuid4().hex[:8]}"
    
    print("\n" + "=" * 80)
    print("CONCURRENT MULTI-AGENT ORCHESTRATION TEST")
    print("=" * 80)
    
    log(f"🧪 Starting test with thread ID: {thread_id}")
    log("🧪 This test demonstrates how multiple agents can process the same request concurrently")
    log("🧪 Each agent will provide its specialized response, and results will be combined")
    
    # Test query that should engage multiple agents
    user_message = """
    I'm developing a web application that will process financial data. 
    I need to understand:
    1. How to structure the database for optimal query performance
    2. What security measures to implement for sensitive financial data
    3. How to visualize transaction patterns effectively
    """
    
    log(f"🧪 User message: {user_message}")
    log("🧪 Beginning orchestration process...")
    
    # Capture full output
    full_output = []
    
    def verbose_stream_callback(chunk):
        full_output.append(chunk)
        print(chunk, end="", flush=True)
    
    start_time = time.time()
    response = orchestrator.orchestrate(
        thread_id=thread_id, 
        user_message=user_message,
        stream_callback=verbose_stream_callback
    )
    elapsed = time.time() - start_time
    
    log(f"🧪 Orchestration completed in {elapsed:.2f} seconds")
    log(f"🧪 Response length: {len(''.join(full_output))} characters")
    
    # Print complete response for analysis
    print("\n\n" + "=" * 60)
    print("COMPLETE RESPONSE:")
    print("=" * 60)
    print(response)
    print("=" * 60)
    
    log("🧪 Test complete!")

if __name__ == "__main__":
    orchestrator = setup_test()
    run_test(orchestrator) 