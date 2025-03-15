../moya/moya/orchestrators/base_orchestrator.py

```python
"""
BaseOrchestrator for Moya.

Defines an abstract class that orchestrates conversations between
users (or other agents) and registered Moya agents.
"""

import abc
from typing import Any, Optional

from moya.registry.agent_registry import AgentRegistry


class BaseOrchestrator(abc.ABC):
    """
    BaseOrchestrator coordinates message flow among one or more agents
    in response to user or agent-initiated messages.

    Responsibilities:
    - Receiving and parsing incoming messages,
    - Selecting appropriate agent(s) to handle the message,
    - Optionally storing conversation history in memory,
    - Returning the aggregated response to the caller or next step.

    Concrete subclasses must implement the 'orchestrate' method (or
    a similar interface) to define how messages are routed.
    """

    def __init__(
        self,
        agent_registry: AgentRegistry,
        config: Optional[Any] = None,
        **kwargs
    ):
        """
        :param agent_registry: The AgentRegistry instance used to discover or retrieve agents.
        :param config: Optional orchestrator configuration parameters.
        :param kwargs: Additional orchestrator-specific parameters.
        """
        self.agent_registry = agent_registry
        self.config = config or {}

    @abc.abstractmethod
    def orchestrate(self, thread_id: str, user_message: str, stream_callback=None, **kwargs) -> str:
        """
        Orchestrate conversation flow given a user message (or agent-to-agent message).
        Subclasses decide which agent(s) to call and how to combine responses.

        :param thread_id: The identifier of the conversation thread.
        :param user_message: The latest message from the user (or external actor).
        :param stream_callback: Optional callback function for streaming responses.
        :param kwargs: Additional context that may be relevant (e.g., user_id, metadata).
        :return: A string response (could be aggregated from multiple agents).
        """
        raise NotImplementedError("Subclasses must implement orchestrate().")
```

../moya/moya/orchestrators/react_orchestrator.py

```python
"""
ReActOrchestrator for Moya.

An implementation of an orchestrator that follows the ReAct framework:
- Thought: Explain reasoning towards solving the task and the assistant to assign the task to.
- Action: Provide the question or task to assign to the assistant.
- Observation: Automatically generated based on the responses of the assistants.
"""

from typing import Optional

from moya.agents.base_agent import Agent
from moya.orchestrators.base_orchestrator import BaseOrchestrator
from moya.registry.agent_registry import AgentRegistry
from moya.classifiers.base_classifier import BaseClassifier
import os


class ReActOrchestrator(BaseOrchestrator):
    """
    An orchestrator that follows the ReAct framework to handle user messages.
    """

    def __init__(
        self,
        agent_registry: AgentRegistry,
        classifier: BaseClassifier,
        llm_agent: Agent,
        default_agent_name: Optional[str] = None,
        config: Optional[dict] = {},
        verbose=False
    ):
        """
        :param agent_registry: The AgentRegistry to retrieve agents from.
        :param classifier: The classifier to use for agent selection.
        :param llm_agent: The LLM agent to generate responses.
        :param default_agent_name: The default agent to fall back on if no specialized match is found.
        :param config: Optional dictionary for orchestrator configuration.
        """
        super().__init__(agent_registry=agent_registry, config=config)
        self.classifier = classifier
        self.default_agent_name = default_agent_name

        self.verbose = verbose
        self.llm_agent = llm_agent

    def orchestrate(self, thread_id: str, user_message: str, stream_callback=None, **kwargs) -> str:
        """
        The main orchestration method following the ReAct framework.
        """
        self.max_steps = self.config.get("max_steps", 5)

        observation = user_message

        while not self._is_final_answer(observation, user_message) and self.max_steps > 0:
            self.log(message=f"Step {self.config.get('max_steps', 5) - self.max_steps}")
            self.max_steps -= 1
            thought = self._generate_thought(observation, user_message)
            action = self._determine_action(thought)
            observation = self._execute_action(action)
            self.log(message="new_line")

        self.log(message="new_line\n=== Final Answer ===")
        return self._generate_final_answer(observation)

    def _call_llm(self, system_prompt: str, message: str) -> str:
        """
        Call the LLM to generate a response.
        """
        self.llm_agent.system_prompt = system_prompt
        response = self.llm_agent.handle_message(message)
        # print(response)
        return response

    def _determine_action(self, thought: str) -> str:
        """
        Determine the next action based on the current thought.
        """
        available_agents = self.agent_registry.list_agents()
        agent_name = self.classifier.classify(
            thought, available_agents=available_agents)
        if not agent_name:
            agent_name = self.default_agent_name
        task = self._generate_task(thought, agent_name)
        task = task.replace("task: ", "").replace("Task: ", "").strip()
        action = f"  agent: {agent_name}\n  task: {task}"

        self.log(message=f"{thought}\n{action}")
        return action

    def _generate_task(self, thought: str, agent_name: str) -> str:
        """
        Generate the task based on the thought.
        """
        system_prompt = """Use the agent details along with the observation to generate a descriptive task. NOTE THAT YOU SHOULD ONLY TELL THE AGENT WHAT TO DO, NOT HOW TO DO IT."""

        agent_description = self.agent_registry.get_agent(agent_name).description
        user_message = f"Thought: {thought}. Agent Description: {agent_description}"
        return self._call_llm(system_prompt, user_message)

    def _execute_action(self, action: str) -> str:
        """
        Execute the action and return the observation.
        """
        agent_name, task_description = self._parse_action(action)

        if task_description == "final_answer":
            return task_description

        agent = self.agent_registry.get_agent(agent_name)
        response = agent.handle_message(task_description)

        return self._generate_observation(response)

    def _parse_action(self, action: str) -> tuple:
        """
        Parse the action string to extract the agent name and task description.
        """
        lines = action.split('\n')
        agent_name = lines[0].split(': ')[1]
        task_description = lines[1].split(': ')[1]
        return agent_name, task_description

    def _generate_thought(self, observation: str, user_query: str) -> str:
        """
        Generate the next thought based on the observation.
        """
        system_prompt = """You are an Orchestrator that follows the ReAct framework.
        You will be provided with an observation for the user query.
        Based on the observation, generate a thought to determine the next action.
        You can only think in English; for other languages, first translate the observation to English, perform the thought process, and then use the specific language agent."""

        user_message = f"Observation: {observation}, User Query: {user_query}"
        return self._call_llm(system_prompt, user_message)

    def _is_final_answer(self, observation: str, user_query: str) -> bool:
        """
        Determine if the observation contains the final answer.
        """
        system_prompt = """You will be provided with an observation. If the observation seems to contain the answer to the user query, return 'final_answer', else return null."""

        if observation == user_query:
            return False

        user_message = f"Observation: {observation}, User Query: {user_query}"
        response = self._call_llm(system_prompt, user_message)
        self.log(message=f"Is final answer: {'yes' if response == 'final_answer' else 'no'}")
        return response == "final_answer"

    def _generate_observation(self, response: str) -> str:
        """
        Generate the observation based on the agent's response.
        """
        observation = f"Observation: {response}"
        temp_obs = observation.replace("\n", " ")
        if len(observation) > 100:
            self.log(message=temp_obs[:50] + "..." + temp_obs[-50:])
        else:
            self.log(message=temp_obs)
        return observation

    def _generate_final_answer(self, response: str) -> str:
        """
        Generate the final answer based on the agent's response.
        """
        return response.replace("Observation: ", "")

    def log(self, message: str):
        """
        Log the iteration message.
        """
        if self.verbose:
            messages = message.split('\n')
            for message in messages:
                cleaned_message = message.replace("\n", "").strip()
                if cleaned_message == 'new_line':
                    print("\n")
                elif cleaned_message:
                    print("    [Orchestrator]: ", message)
```

../moya/moya/orchestrators/simple_orchestrator.py

```python
"""
SimpleOrchestrator for Moya.

A reference implementation of a basic orchestrator that:
- Selects a single agent or a set of agents based on naive matching,
- Calls handle_message on the selected agent(s),
- Returns the response(s).
"""

from typing import Optional
from moya.orchestrators.base_orchestrator import BaseOrchestrator
from moya.registry.agent_registry import AgentRegistry


class SimpleOrchestrator(BaseOrchestrator):
    """
    A naive orchestrator that picks a single agent or a simple list of
    agents to handle each user message. The logic here can be as simple
    or as advanced as needed for demonstration.
    """

    def __init__(
        self,
        agent_registry: AgentRegistry,
        default_agent_name: Optional[str] = None,
        config: Optional[dict] = None
    ):
        """
        :param agent_registry: The AgentRegistry to retrieve agents from.
        :param default_agent_name: The default agent to fall back on if no specialized match is found.
        :param config: Optional dictionary for orchestrator configuration.
        """
        super().__init__(agent_registry=agent_registry, config=config)
        self.default_agent_name = default_agent_name

    def orchestrate(self, thread_id: str, user_message: str, stream_callback=None, **kwargs) -> str:
        """
        The main orchestration method. In this simple implementation, we:
          1. Attempt to find an agent by name if one is specified in kwargs,
             else use the default agent if available,
             else just pick the first agent in the registry (if any).
          2. Pass the user_message to the chosen agent's handle_message().
          3. Return the agent's response.
          4. (Optionally) store the conversation message in memory via a MemoryTool.

        :param thread_id: The conversation thread ID.
        :param user_message: The message from the user.
        :param stream_callback: Optional callback function for streaming responses.
        :param kwargs: Additional context (e.g., 'agent_name' to override which agent to call).
        :return: The response from the chosen agent.
        """
        # 1. Determine which agent to call
        agent_name = kwargs.get("agent_name")
        agent = None

        if agent_name:
            agent = self.agent_registry.get_agent(agent_name)
        elif self.default_agent_name:
            agent = self.agent_registry.get_agent(self.default_agent_name)
        else:
            # If no default is specified, just pick the first agent available
            agent_list = self.agent_registry.list_agents()
            if (agent_list):
                agent = self.agent_registry.get_agent(agent_list[0])

        if not agent:
            return "[No suitable agent found to handle message.]"

        # 2. We could store the incoming user message in memory via a MemoryTool (optional):
        #    If agent.tool_registry is available, we can call a MemoryTool method to store the user's message.
        if agent.tool_registry:
            try:
                agent.call_tool(
                    tool_name="MemoryTool",
                    method_name="store_message",
                    thread_id=thread_id,
                    sender="user",
                    content=user_message
                )
            except Exception as e:
                print(f"Error storing user message: {e}")

        # 3. Let the agent handle the message with streaming support
        if stream_callback:
            response = ""
            for chunk in agent.handle_message_stream(user_message, thread_id=thread_id, **kwargs):
                stream_callback(chunk)
                response += chunk
        else:
            response = agent.handle_message(user_message, thread_id=thread_id, **kwargs)

        # 4. Store the agent's response in memory (optional)
        if agent.tool_registry:
            try:
                agent.call_tool(
                    tool_name="MemoryTool",
                    method_name="store_message",
                    thread_id=thread_id,
                    sender=agent.agent_name,
                    content=response
                )
            except Exception as e:
                print(f"Error storing agent response: {e}")

        # 5. Return the agent's response
        return response
```

../moya/moya/orchestrators/__init__.py

```python
```

../moya/moya/orchestrators/multi_agent_orchestrator.py

```python
from typing import Optional
from moya.orchestrators.base_orchestrator import BaseOrchestrator
from moya.registry.agent_registry import AgentRegistry
from moya.classifiers.base_classifier import BaseClassifier

class MultiAgentOrchestrator(BaseOrchestrator):
    """
    An orchestrator that uses a classifier to route messages to appropriate agents.
    """

    def __init__(
        self,
        agent_registry: AgentRegistry,
        classifier: BaseClassifier,
        default_agent_name: Optional[str] = None,
        config: Optional[dict] = None
    ):
        """
        :param agent_registry: The AgentRegistry to retrieve agents from
        :param classifier: The classifier to use for agent selection
        :param default_agent_name: Fallback agent if classification fails
        :param config: Optional configuration dictionary
        """
        super().__init__(agent_registry=agent_registry, config=config)
        self.classifier = classifier
        self.default_agent_name = default_agent_name

    def orchestrate(self, thread_id: str, user_message: str, stream_callback=None, **kwargs) -> str:
        """
        Orchestrate the message handling using intelligent agent selection.

        :param thread_id: The conversation thread ID
        :param user_message: The message from the user
        :param stream_callback: Optional callback for streaming responses
        :param kwargs: Additional context
        :return: The response from the chosen agent
        """
        # Get available agents
        available_agents = self.agent_registry.list_agents()
        if not available_agents:
            return "[No agents available to handle message.]"

        # Use classifier to select agent
        agent_name = kwargs.get("agent_name")  # Allow override
        if not agent_name:
            agent_name = self.classifier.classify(
                message=user_message,
                thread_id=thread_id,
                available_agents=available_agents
            )
            
        # Fallback to default if classification fails
        if not agent_name and self.default_agent_name:
            agent_name = self.default_agent_name

        # Get the agent
        agent = self.agent_registry.get_agent(agent_name) if agent_name else None
        if not agent:
            return "[No suitable agent found to handle message.]"

        # Add agent name prefix for the response
        agent_prefix = f"[{agent.agent_name}] "

        # Store user message in memory if possible
        if agent.tool_registry:
            try:
                agent.call_tool(
                    tool_name="MemoryTool",
                    method_name="store_message",
                    thread_id=thread_id,
                    sender="user",
                    content=user_message
                )
            except Exception as e:
                print(f"Error storing user message: {e}")

        # Handle message with streaming support
        if stream_callback:
            # Send agent prefix first
            stream_callback(agent_prefix)
            response = agent_prefix
            
            for chunk in agent.handle_message_stream(user_message, thread_id=thread_id, **kwargs):
                stream_callback(chunk)
                response += chunk
        else:
            agent_response = agent.handle_message(user_message, thread_id=thread_id, **kwargs)
            response = agent_prefix + agent_response

        # Store agent response in memory if possible
        if agent.tool_registry:
            try:
                agent.call_tool(
                    tool_name="MemoryTool",
                    method_name="store_message",
                    thread_id=thread_id,
                    sender=agent.agent_name,
                    content=response
                )
            except Exception as e:
                print(f"Error storing agent response: {e}")

        return response
```

