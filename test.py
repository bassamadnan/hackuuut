"""
Interactive chat example using Azure OpenAI agents with specialized functions.
"""

import os
import random
from moya.conversation.thread import Thread
from moya.tools.base_tool import BaseTool
from moya.tools.ephemeral_memory import EphemeralMemory
from moya.tools.tool_registry import ToolRegistry
from moya.registry.agent_registry import AgentRegistry
from moya.orchestrators.multi_agent_orchestrator import MultiAgentOrchestrator
from moya.agents.azure_openai_agent import AzureOpenAIAgent, AzureOpenAIAgentConfig
from moya.conversation.message import Message
from moya.classifiers.llm_classifier import LLMClassifier


def reverse_text(text: str) -> str:
    """
    Reverse the given text.

    Args:
        text (str): The text to reverse.

    Returns:
        str: The reversed text.
    """
    return f"{text[::-1]}"


def fetch_weather_data(location: str) -> str:
    """
    Fetch random weather data for a given location.

    Args:
        location (str): The location to fetch weather data for.

    Returns:
        str: A string describing the weather in the given location.
    """
    weather_list = ["sunny", "rainy", "cloudy", "windy"]
    # Pick a random weather condition
    return f"The weather in {location} is {random.choice(weather_list)}."


def setup_memory_components():
    """Set up memory components for the agents."""
    tool_registry = ToolRegistry()
    EphemeralMemory.configure_memory_tools(tool_registry)
    
    # Register reverse text tool
    reverse_text_tool = BaseTool(
        name="reverse_text_tool",
        description="Tool to reverse any given text",
        function=reverse_text,
        parameters={
            "text": {
                "type": "string",
                "description": "The input text to reverse"
            }
        },
        required=["text"]
    )
    tool_registry.register_tool(reverse_text_tool)

    # Register weather data tool
    fetch_weather_data_tool = BaseTool(
        name="fetch_weather_data_tool",
        description="Tool to fetch weather data for a location",
        function=fetch_weather_data,
        parameters={
            "location": {
                "type": "string",
                "description": "The location to fetch weather data for"
            }
        },
        required=["location"]
    )
    tool_registry.register_tool(fetch_weather_data_tool)
    
    # Print all available tools
    print("=== REGISTERED TOOLS ===")
    for tool in tool_registry.get_tools():
        print(f"- {tool.name}: {tool.description}")
    print("========================")
    
    return tool_registry


def create_reverse_agent(tool_registry):
    """Create an Azure OpenAI agent specialized in text reversal."""
    agent_config = AzureOpenAIAgentConfig(
        agent_name="reverse_agent",
        agent_type="ChatAgent",
        description="Agent specialized in reversing text",
        system_prompt="""You are a specialized agent focused on reversing text.
        You have access to the reverse_text_tool that can reverse any text.
        Always use this tool when someone asks for text to be reversed.
        Be friendly and creative in your responses.""",
        tool_registry=tool_registry,
        model_name="gpt-4o",
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION") or "2024-12-01-preview"
    )

    return AzureOpenAIAgent(config=agent_config)


def create_weather_agent(tool_registry):
    """Create an Azure OpenAI agent specialized in weather information."""
    agent_config = AzureOpenAIAgentConfig(
        agent_name="weather_agent",
        agent_type="ChatAgent",
        description="Agent specialized in providing weather information",
        system_prompt="""You are a specialized agent focused on providing weather information.
        You have access to the fetch_weather_data_tool that can get weather data for any location.
        Always use this tool when someone asks about the weather.
        Be helpful and informative in your responses.""",
        tool_registry=tool_registry,
        model_name="gpt-4o",
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION") or "2024-12-01-preview"
    )

    return AzureOpenAIAgent(config=agent_config)


def create_classifier_agent(tool_registry):
    """Create a classifier agent to route messages to the appropriate agent."""
    agent_config = AzureOpenAIAgentConfig(
        agent_name="classifier",
        agent_type="AgentClassifier",
        description="Classifier for routing messages to specialized agents",
        system_prompt="""You are a classifier. Your job is to determine the best agent based on the user's message:
        1. If the message asks about reversing text or contains words like 'reverse', 'backwards', or similar, return 'reverse_agent'
        2. If the message asks about weather, climate, or mentions a location in context of weather, return 'weather_agent'
        3. For any other query, return 'reverse_agent' as the default
        
        Analyze the intent of the message carefully.
        Return only the agent name as specified above.""",
        tool_registry=tool_registry,
        model_name="gpt-4o",
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION") or "2024-12-01-preview"
    )

    return AzureOpenAIAgent(config=agent_config)


def setup_orchestrator():
    """Set up the multi-agent orchestrator with all components."""
    # Set up shared components
    tool_registry = setup_memory_components()

    # Create agents
    reverse_agent = create_reverse_agent(tool_registry)
    weather_agent = create_weather_agent(tool_registry)
    classifier_agent = create_classifier_agent(tool_registry)

    # Set up agent registry
    registry = AgentRegistry()
    registry.register_agent(reverse_agent)
    registry.register_agent(weather_agent)
    
    # Print registered agents
    print("=== REGISTERED AGENTS ===")
    for agent in registry.list_agents():
        print(f"- {agent.name}: {agent.description}")
    print("=========================")

    # Create and configure the classifier
    classifier = LLMClassifier(classifier_agent, default_agent="reverse_agent")

    # Create the orchestrator
    orchestrator = MultiAgentOrchestrator(
        agent_registry=registry,
        classifier=classifier,
        default_agent_name="reverse_agent"
    )

    return orchestrator


def format_conversation_context(messages):
    """Format conversation history for context."""
    context = "\nPrevious conversation:\n"
    for msg in messages:
        sender = "User" if msg.sender == "user" else "Assistant"
        context += f"{sender}: {msg.content}\n"
    return context


def main():
    # Set up the orchestrator and all components
    orchestrator = setup_orchestrator()
    thread_id = "multi_agent_conversation"

    print("Starting multi-agent chat (type 'exit' to quit)")
    print("You can ask for weather information or text reversal")
    print("-" * 50)

    def stream_callback(chunk):
        print(chunk, end="", flush=True)

    # Store initial system message
    EphemeralMemory.store_message(thread_id=thread_id, sender="system", content=f"Starting conversation, thread ID = {thread_id}")

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

        # Determine which agent to use (for logging purposes)
        selected_agent = orchestrator.classifier.classify(user_message)
        print(f"\n[DEBUG] Selected agent: {selected_agent}")
        
        # Print Assistant prompt and get response
        print("\nAssistant: ", end="", flush=True)
        response = orchestrator.orchestrate(
            thread_id=thread_id,
            user_message=enriched_input,
            stream_callback=stream_callback
        )
        print()  # New line after response
        
        # Store the assistant's response
        EphemeralMemory.store_message(thread_id=thread_id, sender="assistant", content=response)


if __name__ == "__main__":
    main()