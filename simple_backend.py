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

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("simple-agent-demo-backend")

# Initialize FastAPI
app = FastAPI(title="Simple Agent Demo Backend")

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

# Mock data for the simple demo
mock_message_sequence = [
    # Initial classifier message
    {
        "id": "classifier-1",
        "role": "assistant",
        "agent": "classifier",
        "content": "I'll help analyze this customer service issue. Based on the description, I'll start by identifying the nature of the problem and relevant customer history. Let me coordinate with the appropriate specialized agents.",
        "timestamp": None, 
        "iteration": 1
    },
    
    # First classifier decision - selecting only two agents initially
    {
        "id": "classifier-decision-1",
        "role": "assistant",
        "agent": "classifier",
        "content": "Based on the initial description, this appears to be a product return issue. I'll engage our returns policy agent and customer history agent to gather the necessary information for the first phase of analysis.",
        "timestamp": None,
        "iteration": 1
    },
    
    # First iteration messages - only two agents
    {
        "id": "returns-agent-1",
        "role": "assistant",
        "agent": "returns_agent",
        "content": """# Returns Policy Analysis

I've reviewed our returns policy for the circumstances described:

## Policy Details
- Standard return window: 30 days from purchase
- Extended holiday return window: 60 days (for purchases between Nov 1-Dec 25)
- Electronics have a modified 15-day return window
- Items must be unopened and in original packaging for full refund

## Customer Situation Evaluation
- Product: Wireless headphones (electronics category)
- Purchase date: January 10, 2023
- Return request date: January 28, 2023
- Return reason: "Doesn't meet expectations"
- Current status: Outside standard 15-day electronics return window

While the customer is outside our standard electronics return window by 3 days, I recommend evaluating their purchase history and loyalty status before making a final determination.

NEXT_STEP: We should consult the customer history to evaluate their loyalty status and previous return patterns.
""",
        "timestamp": None,
        "iteration": 1
    },
    
    {
        "id": "customer-agent-1",
        "role": "assistant",
        "agent": "customer_agent",
        "content": """# Customer History Analysis

I've analyzed this customer's profile and purchase history:

## Customer Profile
- Name: Alex Johnson
- Member since: 2018 (5 years)
- Loyalty tier: Gold
- Lifetime value: $3,875

## Purchase History
- Total orders: 47
- Average order value: $82.45
- Recent purchases (last 90 days): 5 orders totaling $437.60

## Return History
- Total returns: 2 (4.2% return rate - below average)
- Last return: Over 18 months ago
- Return reasons: All legitimate product issues

This is a high-value, loyal customer with minimal return history. Their return rate is significantly below our average of 12%, and they've consistently made purchases over a 5-year period.

Based on their Gold tier status and excellent purchase-to-return ratio, I recommend making an exception to our standard return policy.

NEXT_STEP: I suggest checking the inventory and shipping implications for this potential return.
""",
        "timestamp": None,
        "iteration": 1
    },

    # After the first iteration's messages, classifier makes a decision to add another agent
    {
        "id": "classifier-decision-2",
        "role": "assistant",
        "agent": "classifier",
        "content": "Based on the initial analysis, this is a loyal customer outside our standard return window. Before making a final decision, I'll engage our inventory agent to determine product restocking implications, while continuing with returns policy and customer history agents for additional context.",
        "timestamp": None,
        "iteration": 1
    },
    
    # Type iteration to indicate end of iteration 1
    {
        "type": "iteration", 
        "iteration": 1
    },
    
    # Second iteration messages - adding inventory agent
    {
        "id": "returns-agent-2",
        "role": "assistant",
        "agent": "returns_agent",
        "content": """# Exception Policy Evaluation

I've examined our exception policies for high-tier customers:

## Gold Member Benefits
- Extended return window: +10 days beyond standard policy
- Waived restocking fees for returns
- Free return shipping

## Policy Application
- Original return window (electronics): 15 days
- Gold member extension: +10 days
- Adjusted window: 25 days total
- Current status: Customer is within the adjusted Gold window (18 days since purchase)

According to our Gold member benefits, this customer qualifies for the extended return window. They are within the 25-day adjusted timeframe, even for electronics.

Additionally, as a Gold member, they are eligible for:
1. No restocking fee (normally 15% for opened electronics)
2. Free return shipping

CONTINUE: I recommend approving this return based on policy guidelines for Gold members.
""",
        "timestamp": None,
        "iteration": 2
    },
    
    {
        "id": "customer-agent-2",
        "role": "assistant",
        "agent": "customer_agent",
        "content": """# Customer Retention Analysis

Looking deeper into this customer's engagement patterns:

## Recent Engagement Metrics
- Website visits (last 30 days): 15
- Cart abandonment: 2 instances
- Wish list items: 7 products (total value: $634)
- Email open rate: 87% (well above average)

## Risk Assessment
- Churn probability if return denied: 68%
- Predicted lifetime value if retained: Additional $2,200 over next 2 years
- Probability of negative review if denied: 74%

This customer shows strong engagement with our platform and has several high-value items in their wish list. Denying this return request could significantly impact their loyalty and future purchasing behavior.

Additionally, our customer satisfaction data shows that accommodating reasonable return requests for loyal customers increases their subsequent spending by an average of 18%.

NEXT_STEP: I recommend checking inventory status to ensure this return can be processed efficiently.
""",
        "timestamp": None,
        "iteration": 2
    },
    
    {
        "id": "inventory-agent-2",
        "role": "assistant",
        "agent": "inventory_agent",
        "content": """# Inventory Impact Analysis

I've analyzed the inventory implications for this potential return:

## Product Details
- SKU: WH-5000-BLK
- Description: Premium Wireless Headphones (Black)
- Current stock level: 37 units
- Restock threshold: 15 units
- Sales velocity: 8 units/week

## Return Processing
- Resell potential: High (if unopened)
- Inspection requirements: Standard electronics check
- Processing time: 1-2 business days
- Restocking timeline: Same day if unopened

## Financial Impact
- Product cost: $89.99
- Refund amount: $149.99
- Restocking cost: $4.50
- Net impact: -$64.50

From an inventory perspective, accepting this return presents minimal operational challenges. We have sufficient stock levels, and this is a high-demand product that can be quickly reintegrated into inventory if in good condition.

The only consideration is whether the unit has been opened, which would require additional testing before restocking. However, even with testing, our current warehouse capacity can accommodate this process without delays.

NEXT_STEP: We should consult with the shipping agent to arrange the return logistics.
""",
        "timestamp": None,
        "iteration": 2
    },
    
    # Classifier decision after second iteration
    {
        "id": "classifier-decision-3",
        "role": "assistant",
        "agent": "classifier",
        "content": "We've confirmed this is a loyal Gold member who qualifies for extended returns, and inventory can easily accommodate the return. For the final phase, I'll engage our shipping agent to handle logistics while removing the customer history agent as we have sufficient information about the customer already. The returns policy agent should remain to provide the final approval guidance.",
        "timestamp": None,
        "iteration": 2
    },
    
    # Type iteration to indicate end of iteration 2
    {
        "type": "iteration", 
        "iteration": 2
    },
    
    # Third iteration messages - removing customer agent, adding shipping agent
    {
        "id": "returns-agent-3",
        "role": "assistant",
        "agent": "returns_agent",
        "content": """# Final Return Recommendation

After reviewing all aspects of this case, here's my final assessment:

## Policy Compliance
- Customer is within Gold member extended return window
- All Gold member benefits apply (no restocking fee, free return shipping)
- Exception is fully supported by existing policies

## Approval Details
- Full refund amount: $149.99
- Processing priority: High
- Special notes: Add courtesy note acknowledging customer loyalty

## Required Actions
1. Issue return authorization code: RET-G23-7891
2. Email prepaid return label to customer
3. Expedite refund processing upon receipt
4. Add 500 loyalty points bonus for inconvenience

Based on our policy guidelines and the customer's loyalty status, I fully approve this return request. This decision aligns with both our policy exceptions for Gold members and our customer retention priorities.

CONTINUE: The shipping team should now be engaged to coordinate the return logistics.
""",
        "timestamp": None,
        "iteration": 3
    },
    
    {
        "id": "shipping-agent-3",
        "role": "assistant",
        "agent": "shipping_agent",
        "content": """# Return Shipping Logistics

I've prepared the return shipping logistics for this case:

## Return Label Details
- Carrier: FedEx
- Service: 2Day (Gold member benefit)
- Tracking prefix: RTN-FDX-
- Insurance: Included for full value
- Return address: Central Returns Facility (Dallas)

## Customer Instructions
- Custom email template: GOLD-RETURN-ELECTRONICS
- Step-by-step packaging guidelines included
- Drop-off locations map link personalized to customer's address
- Optional pickup scheduling available

## Internal Processing
- Expected arrival window: 3-5 business days
- Priority code added: GOLD-LOYAL-5YR
- Automated refund trigger upon scan-in

I've generated a prepaid return shipping label and prepared the customer communication with clear instructions. The return package will be flagged for priority handling at our returns center, ensuring expedited processing.

The customer will receive an automatic confirmation when the package is scanned by FedEx, along with tracking updates throughout the return shipping process.

NEXT_STEP: We should provide a complete resolution summary to the customer.
""",
        "timestamp": None,
        "iteration": 3
    },
    
    # Classifier summarizes the solution
    {
        "id": "classifier-decision-4",
        "role": "assistant",
        "agent": "classifier",
        "content": "All necessary agents have provided their input for resolving this return request. I will now prepare the final resolution summary without the need for additional agents.",
        "timestamp": None,
        "iteration": 3
    },
    
    # Type iteration to indicate end of iteration 3
    {
        "type": "iteration", 
        "iteration": 3
    },
    
    # Final summary message
    {
        "id": "summary-1",
        "role": "assistant",
        "agent": "classifier",
        "content": """# Return Request Resolution: Approved

## Summary of Decision
We've approved a full refund for Alex Johnson's wireless headphones return despite being outside the standard 15-day electronics return window. This decision is based on:

1. **Customer Status**: Gold tier loyalty member (5-year history)
   - Qualifies for +10 day return window extension
   - Return falls within this extended window (18 days vs. 25 allowed)

2. **Customer Value**:
   - Loyal customer with 47 total orders and $3,875 lifetime value
   - Minimal return history (only 2 previous returns)
   - High engagement metrics and potential future purchases

3. **Inventory & Operations**:
   - Product easily reintegrated into inventory
   - High-demand item with strong resell potential
   - Minimal operational impact to process this return

## Action Plan
1. **Returns Team**: Process full refund of $149.99 with no restocking fee
2. **Shipping Team**: Send prepaid FedEx 2Day return label
3. **Customer Service**: Add 500 bonus loyalty points and personalized note

## Business Impact
This resolution supports our strategic priorities by:
- Retaining a high-value customer ($2,200+ future projected value)
- Adhering to our Gold member benefits program
- Maintaining positive review metrics and customer satisfaction

The resolution is fully approved and follows our established exception policies for loyal customers.
""",
        "timestamp": None,
        "iteration": 3
    }
]

# Simulate running the agent demo
async def run_agent_demo(thread_id: str, user_message: str):
    logger.info(f"Starting simple agent demo with thread_id {thread_id}")
    
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
            delay = 1 if i == 0 else 3 if "NEXT_STEP" in message.get("content", "") else 2
            await asyncio.sleep(delay)
    
    # Complete the session
    sessions[thread_id]["status"] = "complete"
    logger.info(f"Simple agent demo completed for thread_id {thread_id}")

# API Endpoints
@app.get("/")
async def root():
    return {"message": "Simple Agent Demo API is running"}

@app.post("/api/simple_agent_demo/start", response_model=DemoResponse)
async def start_demo(request: DemoRequest, background_tasks: BackgroundTasks):
    thread_id = str(uuid.uuid4())
    background_tasks.add_task(run_agent_demo, thread_id, request.message)
    return {"session_id": thread_id, "status": "started"}

@app.get("/api/simple_agent_demo/status", response_model=StatusResponse)
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
    uvicorn.run("simple_backend:app", host="0.0.0.0", port=8001, reload=True) 