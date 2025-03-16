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

# Import from our test script
from test_concurrent_orchestration import (
    get_ec2_instances, 
    get_billing_summary, 
    get_security_findings, 
    get_cloudwatch_logs
)

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("agent-demo-backend")

# Initialize FastAPI
app = FastAPI(title="Agent Demo Backend")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class DemoRequest(BaseModel):
    message: str

class DemoResponse(BaseModel):
    session_id: str
    status: str

class StatusResponse(BaseModel):
    status: str
    messages: List[Dict[str, Any]]
    iterations: int

# In-memory storage
sessions = {}

# Mock data for the demo
mock_message_sequence = [
    # Initial classifier message
    {
        "id": "classifier-1",
        "role": "assistant",
        "agent": "classifier",
        "content": "I'll help investigate this AWS cost spike by analyzing services causing unusual costs, potential security issues, root causes, and recommending actions. Let me coordinate with specialized agents to get a comprehensive analysis.",
        "timestamp": None, 
        "iteration": 1
    },
    
    # First iteration messages
    {
        "id": "ec2-agent-1",
        "role": "assistant",
        "agent": "ec2_agent",
        "content": """# EC2 Analysis

After analyzing your EC2 instances, I've found concerning patterns:

## Cost Summary
- **Last Month**: $1,100.25
- **Current Month**: $3,200.50 (190.9% increase)
- **Forecasted**: $6,500.25 (exceeds budget of $2,000)

## Key Findings
1. A high-performance **p3.8xlarge** instance was launched on **March 16, 2025** and is running at **100% utilization**
2. This instance has **no tags** assigned and is costing approximately **$25/hour**
3. Several **m5.2xlarge** instances are running at **<10% utilization**
4. **Reserved Instance coverage** has dropped from 65% to 40%

The unusual p3.8xlarge instance is the primary cost driver. It has no owner tag and wasn't launched through our normal provisioning process.

I recommend immediate investigation by the security team. This appears highly unusual and potentially unauthorized.

NEXT_STEP: I suggest looking into security findings and CloudWatch logs for suspicious activities.
""",
        "timestamp": None,
        "iteration": 1
    },
    
    {
        "id": "security-agent-1",
        "role": "assistant", 
        "agent": "security_agent",
        "content": """# Security Analysis

Based on my review of your AWS security configuration and recent activities, I've discovered several concerning issues that may be related to the cost spike:

## Critical Security Findings

1. **Misconfigured Security Group**: Security group `sg-0a12b3c45d6789012` has been modified on **March 15, 2025** to allow unrestricted access (0.0.0.0/0) on ports 22 and 3389.

2. **IAM User Activity**: User `developer` created access keys on **March 15, 2025** and doesn't have MFA enabled. This user has `AdministratorAccess` policy attached.

3. **Unusual API Calls**: Multiple `RunInstances` API calls from an unrecognized IP address `198.51.100.123` (location: Eastern Europe) using the `developer` credentials.

4. **CloudTrail**: Attempts to disable CloudTrail logging on **March 16, 2025** (failed due to organization SCPs).

## Conclusion

These findings strongly suggest a potential security breach. The unusual EC2 instance identified earlier was likely launched by an unauthorized party using compromised credentials.

NEXT_STEP: I recommend checking CloudWatch logs and billing details for additional context.
""",
        "timestamp": None,
        "iteration": 1
    },
    
    {
        "id": "logs-agent-1",
        "role": "assistant",
        "agent": "logs_agent",
        "content": """# CloudWatch Logs Analysis

I've analyzed the CloudWatch logs for suspicious activities around the time of the unauthorized instance launch:

## Significant Findings

1. **Login Attempts**:
   - Multiple failed login attempts to AWS Management Console from IP `198.51.100.123` before a successful login using `developer` account
   - Successful login from this IP occurred at **03:14 UTC on March 15, 2025**

2. **API Activity**:
   - Unusual pattern of API calls searching for EC2 instances with high GPU capacity
   - List of S3 buckets enumerated at **03:17 UTC**
   - Multiple `DescribeInstances` calls followed by `RunInstances` for p3.8xlarge at **03:22 UTC**

3. **Installation Patterns**:
   - CloudWatch agent logs from the p3.8xlarge instance show installation of cryptocurrency mining software
   - High GPU utilization began approximately 10 minutes after instance launch

## Conclusion

The evidence confirms that this is a security incident. The attacker:
1. Compromised the `developer` account (likely through password reuse as no MFA is present)
2. Modified security groups to maintain access
3. Launched a high-powered GPU instance
4. Installed cryptocurrency mining software

This explains both the unusual instance type and the high utilization.

CONTINUE: Let's get billing details to understand the full financial impact.
""",
        "timestamp": None,
        "iteration": 1
    },
    
    {
        "id": "billing-agent-1",
        "role": "assistant",
        "agent": "billing_agent",
        "content": """# Billing Analysis

I've analyzed your AWS billing data to assess the financial impact of this security incident:

## Cost Breakdown

| Service | Last Month | Current Month | Increase |
|---------|------------|--------------|----------|
| EC2 | $950.75 | $2,980.25 | +213.5% |
| Data Transfer | $89.50 | $165.30 | +84.7% |
| Other Services | $60.00 | $54.95 | -8.4% |
| **Total** | **$1,100.25** | **$3,200.50** | **+190.9%** |

## EC2 Cost Details

- **Compromised p3.8xlarge instance**: $1,950.00 (78 hours × $25/hr)
- **Regular EC2 instances**: $1,030.25
- **Total EC2 Costs**: $2,980.25

## Projected Impact

If the p3.8xlarge continues running:
- **Additional daily cost**: $600.00
- **Projected monthly overage**: $18,600.00
- **Potential impact on cash flow**: Significant

## Recommendation

We need immediate action to:
1. Terminate the unauthorized instance after forensic preservation
2. Implement emergency security controls
3. Contact AWS Support about potential service credit due to fraud

This is the first iteration of our analysis. We should now develop a comprehensive remediation plan.

NEXT_STEP: Let's proceed to the next phase of investigation where we should create a detailed remediation plan.
""",
        "timestamp": None,
        "iteration": 1
    },
    
    # After the first iteration's messages, before the iteration marker, add a classifier decision message
    {
        "id": "classifier-decision-1",
        "role": "assistant",
        "agent": "classifier",
        "content": "Based on the initial findings from all agents, I need to continue our investigation with a detailed remediation planning phase. The EC2 instance appears to be compromised, and security vulnerabilities have been identified. I'll select specialized agents to develop a comprehensive remediation plan. NEXT_STEP: Let's proceed to the remediation planning phase.",
        "timestamp": None,
        "iteration": 1
    },
    
    # Type iteration to indicate end of iteration 1
    {
        "type": "iteration", 
        "iteration": 1
    },
    
    # Second iteration messages
    {
        "id": "ec2-agent-2",
        "role": "assistant",
        "agent": "ec2_agent",
        "content": """# EC2 Remediation Plan

Based on our combined findings, here's my recommended EC2 remediation plan:

## Immediate Actions (Next 2 Hours)

1. **Preserve Evidence**:
   - Create a snapshot of the compromised p3.8xlarge instance's EBS volumes
   - Enable memory dump if AWS Nitro Enclaves are enabled
   - Tag all resources related to the incident with "Incident-Response-20250316"

2. **Contain the Breach**:
   - Terminate the compromised p3.8xlarge instance AFTER evidence collection
   - Isolate any potentially affected instances into a secured subnet
   - Update relevant security groups to restrict access to known IPs only

## Short-Term Optimizations (Next 24 Hours)

1. **Right-size Existing Instances**:
   - Scale down 5 underutilized m5.2xlarge instances to m5.large
   - Estimated monthly savings: $750
   
2. **Reserved Instance Optimization**:
   - Convert 20% of on-demand instances to Reserved Instances
   - Estimated monthly savings: $320

## Monitoring Enhancements

1. **Cost Anomaly Detection**:
   - Set up AWS Cost Anomaly Detection with hourly granularity
   - Configure alerts for:
     - Hourly spend exceeding $50
     - Daily spend exceeding $500
     - Any p3/p4/g4 instance launches

2. **Custom CloudWatch Dashboard**:
   - Create dashboard for EC2 instance monitoring with cost metrics
   - Implement automated reporting for idle and underutilized resources

The immediate termination of the compromised instance will stop the ongoing cost increase, while the optimization steps will bring your costs back within budget constraints.

NEXT_STEP: The security team should provide their remediation plan for the compromised credentials and IAM improvements.
""",
        "timestamp": None,
        "iteration": 2
    },
    
    {
        "id": "security-agent-2",
        "role": "assistant",
        "agent": "security_agent",
        "content": """# Security Remediation Plan

Here's my comprehensive security remediation plan to address the breach and prevent future incidents:

## Critical Immediate Actions (0-4 hours)

1. **Contain Compromised Credentials**:
   - Deactivate access keys for user `developer`
   - Force password reset for all IAM users
   - Revoke any active sessions for the compromised account
   - Rotate all console and programmatic credentials for privileged users

2. **Secure Network Configuration**:
   - Revert security group `sg-0a12b3c45d6789012` to its pre-breach configuration
   - Implement Just-in-Time access for administration ports (22, 3389, etc.)
   - Apply NACLs to restrict traffic to/from suspicious IPs
   - Enable VPC Flow Logs for all subnets

## Short-Term Improvements (1-3 days)

1. **IAM Security Hardening**:
   - Enforce MFA for all IAM users with console access
   - Implement role-based access control with temporary credentials
   - Apply least privilege principle across all IAM entities
   - Implement AWS Organizations SCPs to prevent:
     - Security group modifications to allow 0.0.0.0/0
     - CloudTrail disabling
     - Public S3 bucket creation

2. **Detection Capabilities**:
   - Enable GuardDuty with all protection plans
   - Set up CloudTrail insights for API call monitoring
   - Implement IP-based login restrictions where feasible
   - Configure AWS Config rules for continuous compliance monitoring

## Long-Term Strategy (1-4 weeks)

1. **Access Management Overhaul**:
   - Implement SAML-based SSO integration with your identity provider
   - Develop break-glass procedures for emergency access
   - Create comprehensive permission boundaries
   - Implement automated access reviews

2. **Security Testing**:
   - Conduct AWS penetration testing with focus on IAM
   - Perform security assessment of all critical workloads
   - Simulate common attack scenarios to validate controls

The combination of these actions will remediate the current breach and significantly reduce the risk of future security incidents.

CONTINUE: Let's proceed with developing additional monitoring and alerting recommendations.
""",
        "timestamp": None,
        "iteration": 2
    },
    
    {
        "id": "logs-agent-2",
        "role": "assistant",
        "agent": "logs_agent",
        "content": """# Enhanced Monitoring & Alerting Plan

To strengthen your monitoring capabilities and ensure early detection of similar incidents, I recommend implementing the following comprehensive monitoring and alerting strategy:

## CloudWatch Logs Monitoring (1-2 days)

1. **Advanced Log Filters**:
   - Create metric filters for suspicious login patterns:
     * Multiple failed login attempts followed by success
     * Logins from new geographic locations
     * After-hours admin activity
   - Monitor for critical resource creations/modifications:
     * EC2 instances of type p3, p4, g4, etc.
     * Security Group modifications
     * IAM permission changes

2. **Alerting Configuration**:
   - Set up SNS topics for different severity alerts
   - Configure PagerDuty/OpsGenie integration for critical alerts
   - Implement escalation paths for unaddressed alerts

## Custom Monitoring Solutions (3-7 days)

1. **User Behavior Analytics**:
   - Develop baseline profiles for normal user activity
   - Track deviations from established patterns
   - Implement ML-based anomaly detection using CloudWatch Anomaly Detection

2. **Cost-Security Correlation Dashboard**:
   - Build a custom dashboard correlating security events with cost spikes
   - Include metrics for:
     * Resource creation events vs. cost changes
     * Network traffic patterns and associated costs
     * API calls from non-standard sources

## Proactive Testing (Weekly)

1. **Continuous Validation**:
   - Schedule weekly tests of alerting mechanisms
   - Simulate common attack patterns to verify detection
   - Conduct regular table-top exercises for incident response

2. **Response Automation**:
   - Develop AWS Lambda functions to automatically:
     * Isolate potentially compromised resources
     * Capture forensic evidence
     * Restrict suspicious IAM users

This monitoring strategy provides defense-in-depth by correlating signals across logs, IAM activity, and cost data to rapidly identify potential security incidents before they cause significant financial impact.

NEXT_STEP: Let's finalize with billing recommendations and cost controls.
""",
        "timestamp": None,
        "iteration": 2
    },
    
    {
        "id": "billing-agent-2",
        "role": "assistant",
        "agent": "billing_agent",
        "content": """# Cost Control & Financial Recovery Plan

Based on our comprehensive analysis, here's my recommended plan for cost control, budget alignment, and financial recovery:

## Immediate Cost Controls (1-2 days)

1. **Service Quotas & Limits**:
   - Implement EC2 service quotas for GPU instances (p3, p4, g4)
   - Set up Organization-level SCP to require tags for all resource creation
   - Configure AWS Budgets with 80%, 90%, and 100% threshold alerts

2. **AWS Cost Explorer Monitoring**:
   - Create custom reports for daily anomaly detection
   - Configure hourly granularity for EC2 expense monitoring
   - Set up weekly cost trending reports to identify gradual increases

## Financial Recovery Actions (1-7 days)

1. **AWS Support Case**:
   - Create high-priority AWS Support case (Enterprise Support recommended)
   - Request service credits due to fraudulent activity
   - Provide evidence collected by security and logs teams
   - Expected potential recovery: 40-60% of fraudulent charges

2. **Insurance Claim**:
   - Prepare cyber insurance claim documentation
   - Calculate direct and indirect costs of the incident
   - Submit detailed timeline and remediation expenses

## Long-term Cost Optimization (2-4 weeks)

1. **Architectural Improvements**:
   - Implement auto-scaling based on utilization metrics
   - Shift suitable workloads to Spot Instances (50-70% savings)
   - Evaluate Compute Savings Plans for consistent workloads

2. **Governance Framework**:
   - Develop tagging strategy for resource ownership and cost allocation
   - Implement mandatory approval workflow for high-cost resources
   - Create cost center chargebacks for accurate internal billing

3. **Operational Improvements**:
   - Schedule automated instance start/stop for development environments
   - Configure lifecycle policies for EBS snapshots and backups
   - Implement S3 Intelligent Tiering for optimal storage costs

## Summary of Financial Impact

| Action | Estimated Savings/Recovery |
|--------|----------------------------|
| Terminate unauthorized instance | $18,600/month |
| Instance right-sizing | $750/month |
| Reserved Instances | $320/month |
| AWS service credits | $1,170-$1,755 (one-time) |
| Long-term optimizations | $800-$1,200/month |
| **Total Monthly Savings** | **$20,470-$20,870** |

These measures will immediately bring your AWS spending back under control, potentially recover some of the fraudulent charges, and implement a robust cost management framework to prevent similar incidents in the future.
""",
        "timestamp": None,
        "iteration": 2
    },
    
    # After the second iteration's messages, before the iteration marker, add a classifier decision message
    {
        "id": "classifier-decision-2",
        "role": "assistant",
        "agent": "classifier",
        "content": "We now have a comprehensive understanding of the security breach and its implications. The remediation plans from each agent are detailed and actionable. I'll coordinate the final recommendations phase to create a holistic response plan. NEXT_STEP: Let's finalize our recommendations.",
        "timestamp": None,
        "iteration": 2
    },
    
    # Type iteration to indicate end of iteration 2
    {
        "type": "iteration", 
        "iteration": 2
    },
    
    # Third iteration messages
    {
        "id": "ec2-agent-3",
        "role": "assistant",
        "agent": "ec2_agent",
        "content": """# Implementation Timeline

Here's the recommended implementation timeline for the EC2-related remediation steps:

## Immediate (0-2 hours)
- Create snapshots of the compromised p3.8xlarge instance's EBS volumes
- Apply emergency network isolation to the compromised instance
- Prepare scripts for right-sizing the underutilized m5.2xlarge instances

## Short-term (2-24 hours)
- Terminate the compromised instance after evidence collection
- Apply the right-sizing plan to underutilized instances
- Implement tagging enforcement for all new EC2 instances

## Medium-term (1-3 days)
- Configure EC2 Instance Type restrictions via Service Control Policies
- Set up Cost Anomaly Detection with hourly granularity
- Create custom CloudWatch dashboards for instance monitoring

The initial emergency actions will stop the ongoing cost bleeding, while the short and medium-term actions will provide sustained cost optimization and security improvements.

CONTINUE: I recommend finalizing these implementation timelines with input from the other specialized agents.
""",
        "timestamp": None,
        "iteration": 3
    },
    
    {
        "id": "security-agent-3",
        "role": "assistant",
        "agent": "security_agent",
        "content": """# Security Implementation Timeline

Based on our comprehensive findings, here's our security implementation timeline:

## Critical (0-2 hours)
- Deactivate all access keys for the `developer` IAM user
- Force password reset for all IAM users with console access
- Revert the compromised security group to pre-breach configuration
- Enable CloudTrail logging to a secured S3 bucket

## Urgent (2-12 hours)
- Implement emergency IAM policy restrictions
- Deploy temporary IP-based access controls
- Enable GuardDuty with immediate alerting
- Begin forensic investigation of the compromised resources

## High Priority (12-48 hours)
- Enforce MFA for all human IAM users
- Implement SAML-based SSO configuration
- Deploy comprehensive permission boundaries
- Set up automated compliance scanning

This tiered approach addresses the immediate security exposure while establishing the groundwork for a comprehensive security enhancement plan.

NEXT_STEP: We should combine these timelines with the billing recommendations.
""",
        "timestamp": None,
        "iteration": 3
    },
    
    {
        "id": "billing-agent-3",
        "role": "assistant",
        "agent": "billing_agent",
        "content": """# Financial Recovery Timeline

Following our analysis, here's the implementation timeline for financial recovery and cost controls:

## Immediate Financial Actions (0-24 hours)
- Create AWS Support case (Enterprise Support) with all evidence
- Implement hard service quotas for GPU instance types
- Configure AWS Budget alerts at 80%, 90%, and 100% thresholds
- Begin documentation for cyber insurance claim

## Short-term Controls (1-3 days)
- Implement mandatory tagging strategy with cost allocation
- Configure Cost Explorer hourly granularity monitoring
- Create resource lifecycle policies for all environment types
- Set up weekly cost anomaly reports for key stakeholders

## Financial Recovery (5-14 days)
- Submit detailed service credit request to AWS
- Finalize insurance claim documentation
- Implement chargebacks for project-based resource usage
- Present cost optimization plan to leadership

This timeline balances immediate cost containment with longer-term financial governance and recovery efforts.

CONTINUE: Let's finalize the comprehensive implementation plan.
""",
        "timestamp": None,
        "iteration": 3
    },
    
    {
        "id": "logs-agent-3",
        "role": "assistant",
        "agent": "logs_agent",
        "content": """# Monitoring Implementation Timeline

Based on our analysis, here's the implementation timeline for enhanced monitoring controls:

## Immediate Monitoring (0-24 hours)
- Deploy metric filters for suspicious login patterns
- Create CloudWatch alarms for critical infrastructure changes
- Set up SNS topics with escalation paths for high-severity alerts
- Begin baseline creation for normal user activity patterns

## Short-term Enhancements (1-3 days)
- Implement CloudWatch Logs Insights for advanced pattern detection
- Configure VPC Flow Logs with retention policies
- Develop custom security-cost correlation dashboard
- Set up automated reporting for suspicious activity

## Ongoing Monitoring (Weekly)
- Schedule validation tests for alerting mechanisms
- Implement ML-based anomaly detection refinement
- Conduct simulations of common attack patterns
- Review and update correlation rules and alert thresholds

This tiered approach will provide immediate visibility while establishing the foundation for sophisticated ongoing monitoring.

NEXT_STEP: Let's compile our findings into a final implementation roadmap.
""",
        "timestamp": None,
        "iteration": 3
    },
    
    {
        "id": "classifier-decision-3",
        "role": "assistant",
        "agent": "classifier",
        "content": "Now that all specialized agents have provided their implementation timelines, I'll consolidate their findings into a comprehensive roadmap. The security, EC2, billing, and logs teams have all provided detailed timelines that we need to align and prioritize. CONTINUE: I'll now create the final executive summary and implementation roadmap.",
        "timestamp": None,
        "iteration": 3
    },
    
    # Add an iteration marker for iteration 3
    {
        "type": "iteration", 
        "iteration": 3
    },
    
    # Final summary message
    {
        "id": "summary-1",
        "role": "assistant",
        "agent": "classifier",
        "content": """# AWS Cost Spike Investigation: Final Report

## Root Cause Analysis
Our multi-agent investigation has determined that the AWS cost spike was caused by a **security breach**:

1. An attacker compromised the `developer` IAM user account through credential theft
2. The attacker modified security groups to maintain access
3. They launched an expensive p3.8xlarge GPU instance ($25/hour)
4. Cryptocurrency mining software was installed on the instance

## Financial Impact
- **Current excess cost**: $2,100 above normal monthly spend
- **Projected monthly impact if unresolved**: $18,600 additional costs
- **Time to return to normal spending**: 1-2 days after remediation

## Comprehensive Remediation Plan

### Immediate Actions (0-4 hours)
- Preserve forensic evidence from the compromised instance
- Terminate the unauthorized p3.8xlarge instance
- Deactivate compromised IAM credentials
- Restore security group configurations
- Implement emergency network controls

### Short-term Actions (1-3 days)
- Enforce MFA for all IAM users
- Implement strict permission boundaries
- Optimize underutilized EC2 instances
- Deploy enhanced monitoring tools
- Open AWS Support case for service credits

### Long-term Strategy (1-4 weeks)
- Implement comprehensive IAM reforms
- Deploy advanced threat detection
- Develop cost-security correlation monitoring
- Establish robust cost control governance
- Create automated response playbooks

## Expected Outcomes
- Immediate cost reduction to below budget levels
- Potential recovery of 40-60% of fraudulent charges
- 80% reduction in similar security incident risk
- Improved visibility across security and cost dimensions

This incident highlights the critical intersection between security and cost management in cloud environments. The remediation plan addresses both immediate concerns and establishes safeguards against future incidents.
""",
        "timestamp": None,
        "iteration": 3
    }
]

# Simulate running the agent demo
async def run_agent_demo(thread_id: str, user_message: str):
    logger.info(f"Starting agent demo with thread_id {thread_id}")
    
    # Initialize session data
    sessions[thread_id] = {
        "status": "running",
        "messages": [],
        "iterations": 0,
        "start_time": time.time()
    }
    
    # Simulate message sequence with delays
    for i, message in enumerate(mock_message_sequence):
        # Add timestamp to message
        if message.get("role") == "assistant":
            message["timestamp"] = datetime.now().isoformat()
            
        # Check for iteration marker
        if message.get("type") == "iteration":
            sessions[thread_id]["iterations"] = message["iteration"]
            await asyncio.sleep(2)  # Pause between iterations
        else:
            # Add message to session
            sessions[thread_id]["messages"].append(message)
            
            # Simulate processing time - longer for more complex messages
            delay = 1 if i == 0 else 5 if "NEXT_STEP" in message.get("content", "") else 3
            await asyncio.sleep(delay)
    
    # Complete the session
    sessions[thread_id]["status"] = "complete"
    logger.info(f"Agent demo completed for thread_id {thread_id}")

# API Endpoints
@app.get("/")
async def root():
    return {"message": "Agent Demo API is running"}

@app.post("/api/agent_demo/start", response_model=DemoResponse)
async def start_demo(request: DemoRequest, background_tasks: BackgroundTasks):
    thread_id = str(uuid.uuid4())
    background_tasks.add_task(run_agent_demo, thread_id, request.message)
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
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=True) 