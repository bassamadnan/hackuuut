"""
Test script for the concurrent multi-agent orchestrator with AWS cloud management scenario.
"""

import os
import time
import uuid
import json
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from moya.agents.azure_openai_agent import AzureOpenAIAgent, AzureOpenAIAgentConfig
from moya.classifiers.llm_classifier_concurrent import LLMClassifierConcurrent
from moya.orchestrators.multi_agent_orchestrator_concurrent import MultiAgentOrchestratorConcurrent
from moya.registry.agent_registry import AgentRegistry
from moya.tools.ephemeral_memory import EphemeralMemory
from moya.tools.tool_registry import ToolRegistry
from moya.tools.base_tool import BaseTool

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

# Create mock AWS data for tools
def generate_mock_ec2_instances():
    """Generate mock EC2 instance data."""
    instance_types = ["t3.micro", "t3.medium", "m5.large", "c5.xlarge", "r5.2xlarge"]
    regions = ["us-east-1", "us-west-2", "eu-west-1"]
    
    instances = []
    for i in range(20):
        uptime = random.randint(1, 90)
        instances.append({
            "InstanceId": f"i-{uuid.uuid4().hex[:8]}",
            "InstanceType": random.choice(instance_types),
            "State": {"Name": "running" if random.random() > 0.2 else "stopped"},
            "Region": random.choice(regions),
            "LaunchTime": (datetime.now() - timedelta(days=uptime)).isoformat(),
            "Tags": [{"Key": "Name", "Value": f"server-{i}"}],
            "Utilization": random.randint(5, 95)
        })
    
    # Add some suspicious instances (recently launched, unusual types, high utilization)
    instances.append({
        "InstanceId": f"i-{uuid.uuid4().hex[:8]}",
        "InstanceType": "p3.8xlarge",  # Expensive GPU instance
        "State": {"Name": "running"},
        "Region": "us-east-1",
        "LaunchTime": (datetime.now() - timedelta(hours=8)).isoformat(),
        "Tags": [],  # No tags
        "Utilization": 100
    })
    
    return instances

def generate_mock_billing_data():
    """Generate mock AWS billing data."""
    services = ["EC2", "S3", "RDS", "Lambda", "CloudWatch", "Data Transfer"]
    
    current_month = {
        "TotalCost": 4250.75,  # Spike in cost
        "LastMonthCost": 1820.50,
        "Forecast": 6500.25,
        "Budget": 2000.00,
        "ServiceBreakdown": []
    }
    
    # Normal service costs
    for service in services:
        if service == "EC2":  # EC2 shows a big spike
            cost = 3200.50
            last_month = 1100.25
        else:
            cost = random.uniform(100, 300)
            last_month = cost * random.uniform(0.8, 1.2)
            
        current_month["ServiceBreakdown"].append({
            "Service": service,
            "Cost": round(cost, 2),
            "LastMonth": round(last_month, 2),
            "PercentChange": round(((cost - last_month) / last_month) * 100, 1)
        })
    
    return current_month

def generate_mock_security_findings():
    """Generate mock AWS security findings."""
    findings = [
        {
            "Id": f"finding-{uuid.uuid4().hex[:8]}",
            "Type": "IAM User has console access with no MFA",
            "Severity": "MEDIUM",
            "Resource": "arn:aws:iam::123456789012:user/developer",
            "CreatedAt": (datetime.now() - timedelta(days=15)).isoformat()
        },
        {
            "Id": f"finding-{uuid.uuid4().hex[:8]}",
            "Type": "Security Group allows unrestricted access (0.0.0.0/0)",
            "Severity": "HIGH",
            "Resource": "arn:aws:ec2:us-east-1:123456789012:security-group/sg-abc123",
            "CreatedAt": (datetime.now() - timedelta(days=30)).isoformat()
        }
    ]
    
    # Add suspicious activity related to our cost spike
    findings.append({
        "Id": f"finding-{uuid.uuid4().hex[:8]}",
        "Type": "Unusual launch of high-performance instance",
        "Severity": "HIGH",
        "Resource": "arn:aws:ec2:us-east-1:123456789012:instance/i-abc123def",
        "CreatedAt": (datetime.now() - timedelta(hours=8)).isoformat(),
        "Context": "User created instance with no resource tags; no similar instances in account history"
    })
    
    return findings

def generate_mock_cloudwatch_logs():
    """Generate mock CloudWatch log events."""
    log_entries = []
    
    # Normal log entries
    for i in range(10):
        log_entries.append({
            "timestamp": int((datetime.now() - timedelta(hours=random.randint(1, 24))).timestamp() * 1000),
            "message": f"INFO: Processed {random.randint(100, 500)} requests successfully",
            "logStream": "application/server-logs"
        })
    
    # Suspicious log entries related to cost spike
    suspicious_times = [(datetime.now() - timedelta(hours=h)).timestamp() * 1000 for h in range(8, 6, -1)]
    suspicious_entries = [
        {
            "timestamp": int(suspicious_times[0]),
            "message": "WARN: Unauthorized access attempt from IP 203.0.113.42",
            "logStream": "auth/server-logs"
        },
        {
            "timestamp": int(suspicious_times[1]),
            "message": "ERROR: Multiple failed login attempts for admin user",
            "logStream": "auth/server-logs"
        },
        {
            "timestamp": int(suspicious_times[0] + 300000),  # 5 minutes later
            "message": "INFO: New EC2 instance i-abc123def launched via API",
            "logStream": "api/resource-events"
        }
    ]
    
    log_entries.extend(suspicious_entries)
    return log_entries

# Mock AWS tools
def get_ec2_instances():
    """Tool: Get list of EC2 instances."""
    return json.dumps(generate_mock_ec2_instances())

def get_billing_summary():
    """Tool: Get AWS billing summary."""
    return json.dumps(generate_mock_billing_data())

def get_security_findings():
    """Tool: Get AWS security findings."""
    return json.dumps(generate_mock_security_findings())

def get_cloudwatch_logs():
    """Tool: Get CloudWatch logs."""
    return json.dumps(generate_mock_cloudwatch_logs())

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
    """Set up the test environment with AWS-focused agents and orchestrator."""
    log("📋 Setting up AWS cloud management test environment...")
    
    # Set up shared components
    tool_registry = ToolRegistry()
    EphemeralMemory.configure_memory_tools(tool_registry)
    agent_registry = AgentRegistry()
    
    log("📋 Configured memory tools and registries", 1)
    
    # Register AWS tools
    aws_tools = [
        BaseTool(name="get_ec2_instances", description="Get list of EC2 instances with details", function=get_ec2_instances),
        BaseTool(name="get_billing_summary", description="Get AWS billing summary and cost breakdown", function=get_billing_summary),
        BaseTool(name="get_security_findings", description="Get AWS security findings and alerts", function=get_security_findings),
        BaseTool(name="get_cloudwatch_logs", description="Get CloudWatch logs with application events", function=get_cloudwatch_logs)
    ]
    
    for tool in aws_tools:
        tool_registry.register_tool(tool)
    
    log("📋 Registered AWS tools", 1)

    # Create classifier agent
    log("📋 Creating classifier agent...", 1)
    classifier_config = AzureOpenAIAgentConfig(
        agent_name="classifier",
        agent_type="Classifier",
        description="Agent selection classifier for AWS operations",
        model_name="gpt-4o-mini",
        system_prompt="""You are a classifier that determines which specialized AWS agents should handle user requests.
        Analyze the user's message and select ALL relevant specialized agents that should process this request concurrently.
        
        Available agents are:
        - ec2_agent: Analyzes EC2 instances, usage patterns, and optimization opportunities
        - billing_agent: Analyzes AWS costs, billing details, and provides budget recommendations
        - security_agent: Identifies security risks, compliance issues, and provides remediation steps
        - logs_agent: Analyzes CloudWatch logs, metrics, and identifies operational issues
        
        Return ONLY agent names separated by commas. For example: "ec2_agent,billing_agent" 
        or "security_agent" or "ec2_agent,billing_agent,security_agent,logs_agent".
        DO NOT include any other text or explanations.""",
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version="2023-07-01-preview"
    )
    classifier_agent = AzureOpenAIAgent(config=classifier_config)
    log("📋 Classifier agent created", 1)

    # Create AWS specialized agents
    aws_agent_configs = [
        ("ec2_agent", "EC2 instance analyzer and optimizer", 
         """You are an AWS EC2 specialist. Analyze EC2 instance data to identify unusual patterns, optimization opportunities, and potential issues.
         Always use the get_ec2_instances tool to retrieve instance data.
         For each analysis:
         1. Identify unusual instances (high-powered instances, recently launched, low utilization)
         2. Suggest optimization opportunities (right-sizing, reserved instances)
         3. Highlight any suspicious activity
         Be precise and data-driven in your analysis."""),
        
        ("billing_agent", "AWS cost analyzer and budget specialist", 
         """You are an AWS billing specialist. Analyze cost data to identify spending anomalies and budget issues.
         Always use the get_billing_summary tool to retrieve billing data.
         For each analysis:
         1. Identify significant cost increases and their causes
         2. Compare against budget and provide forecasts
         3. Recommend cost optimization strategies
         Be precise and data-driven in your analysis."""),
        
        ("security_agent", "AWS security and compliance expert", 
         """You are an AWS security specialist. Analyze security findings to identify risks and compliance issues.
         Always use the get_security_findings tool to retrieve security data.
         For each analysis:
         1. Prioritize findings by severity and potential impact
         2. Identify suspicious or unauthorized activity
         3. Provide clear remediation steps
         Be precise and detail-oriented in your analysis."""),
        
        ("logs_agent", "CloudWatch logs and monitoring expert", 
         """You are an AWS CloudWatch specialist. Analyze log data to identify operational issues and suspicious activity.
         Always use the get_cloudwatch_logs tool to retrieve log data.
         For each analysis:
         1. Identify error patterns and operational issues
         2. Highlight any suspicious activity or security events
         3. Correlate events with timestamps
         Be precise and timeline-focused in your analysis.""")
    ]

    log("📋 Creating AWS specialized agents:", 1)
    for name, desc, prompt in aws_agent_configs:
        log(f"📋 Creating agent: {name}", 2)
        config = AzureOpenAIAgentConfig(
            agent_name=name,
            agent_type="AWSSpecialist",
            description=desc,
            model_name="gpt-4o-mini",
            system_prompt=prompt,
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version="2023-07-01-preview",
            tool_registry=tool_registry,
            is_tool_caller=True
        )
        agent = AzureOpenAIAgent(config=config)
        # Wrap with verbose logging
        wrapped_agent = VerboseAgentWrapper(agent)
        agent_registry.register_agent(wrapped_agent)
        log(f"📋 Agent '{name}' created and registered", 2)

    # Set up the concurrent classifier and orchestrator
    log("📋 Setting up classifier and orchestrator...", 1)
    classifier = VerboseLLMClassifierConcurrent(classifier_agent, default_agent="ec2_agent")
    
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
        default_agent_name="ec2_agent"
    )
    log("📋 Orchestrator created", 1)
    
    return orchestrator

def run_test(orchestrator):
    """Run a test with an AWS cloud management scenario."""
    thread_id = f"aws_incident_{uuid.uuid4().hex[:8]}"
    
    print("\n" + "=" * 80)
    print("AWS CLOUD MANAGEMENT MULTI-AGENT TEST")
    print("=" * 80)
    
    log(f"🧪 Starting test with thread ID: {thread_id}")
    log("🧪 This test simulates an AWS cost spike investigation scenario")
    log("🧪 Multiple specialized agents will analyze the situation concurrently")
    
    # Test query for AWS cost spike investigation
    user_message = """
    We've noticed a significant spike in our AWS costs this month, almost double what we normally spend.
    Our month-to-date bill is already over $4,000 when we normally spend about $2,000 for the entire month.
    
    Can you help investigate what's causing this cost increase? We need to:
    1. Identify what services or resources are causing the unusual costs
    2. Determine if there's any suspicious activity or potential security issues
    3. Get recommendations on how to address the problem immediately
    4. Understand how to prevent this from happening again
    
    Our team is really concerned about this as we're a small startup and this could impact our runway.
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