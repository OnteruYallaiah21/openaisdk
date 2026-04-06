import asyncio
import json
import time
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, Dict, Any
import sys
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()

# Agent framework imports
from agents import Agent, Runner, RunState, RunContextWrapper, function_tool, ModelSettings, ModelSettings  

# --- Business logic: HR Leave Management tools ---
class LeaveRequest(BaseModel):
    employee_name: str
    requested_days: int
    leave_type: str  # e.g., "sick", "vacation", "holiday"

class LeaveBalance(BaseModel):
    employee_name: str
    balance: int  # remaining leave days

# Dummy HR Database responses
HR_DATABASE = {
    "Pavan Kumar Paishetty": LeaveBalance(employee_name="Pavan Kumar Paishetty", balance=5),
    "Preethi": LeaveBalance(employee_name="Preethi", balance=0),
}

# -------------------- Tools --------------------

@function_tool
async def fetch_leave_balance(employee_name: str) -> str:
    """
    Fetch the leave balance for an employee from the HR database.
    Direct responses are not allowed. Must always query this tool.
    """
    print(f"[debug-control {__file__}] fetch_leave_balance called for {employee_name}")
    leave_info = HR_DATABASE.get(employee_name)
    if leave_info:
        return f"{employee_name} has {leave_info.balance} leave days remaining."
    return f"No leave records found for {employee_name}."

@function_tool
async def request_leave(request: LeaveRequest) -> str:
    """
    Process a leave request using the HR database.
    Approves only if balance is sufficient.
    """
    print(f"[debug-control {__file__}] request_leave called for {request.employee_name}")
    balance = HR_DATABASE.get(request.employee_name)
    if not balance:
        return f"No leave records found for {request.employee_name}."
    
    if request.requested_days <= balance.balance:
        balance.balance -= request.requested_days
        return f"Leave approved for {request.requested_days} days. Remaining balance: {balance.balance}."
    else:
        return f"Leave denied. Not enough balance. Current balance: {balance.balance}."

# -------------------- Agent Setup --------------------

async def create_agent():
    """
    Create AI agent for HR leave management.
    Enforces database tool usage for all leave queries.
    """
    # Example: loading a shared model instance (OpenAI)
    from llm_model_config.llm_model_config import ModelSingleton
    model = ModelSingleton.get_instance()
    print("[debug-control] ✅ Model instance loaded for agent")

    agent = Agent(
        name="HR Leave Assistant",
        instructions=(
            "You are an HR assistant. "
            "You must always fetch leave balances and process leave requests using the available tools. "
            "Never provide direct answers."
        ),
        tools=[fetch_leave_balance, request_leave],
        model=model,  # pass model instance here
        model_settings=ModelSettings(tool_choice="required"),
    )
    return agent

# -------------------- Utility Functions --------------------

async def get_user_input(prompt_text: str) -> str:
    """Ask input from command line dynamically."""
    return input(prompt_text)

# -------------------- Main Execution Flow --------------------

async def main():
    agent = await create_agent()

    # Initialize RunContextWrapper for auditing
    run_ctx = RunContextWrapper(agent_name=agent.name)
    
    while True:
        print("\n--- HR Leave Assistant ---")
        question = await get_user_input("Enter your question (or 'exit' to quit): ").strip()
        if question.lower() == "exit":
            break

        start_time = time.time()
        # Run agent with human-in-the-loop enforcement
        result = await Runner.run(agent, question, run_context=run_ctx)
        elapsed = time.time() - start_time

        print(f"[debug-control] Execution Time: {elapsed:.2f}s")

        # Handle interruptions (tool approvals)
        if result.interruptions:
            print("\n⚠️ Tool approval required:")
            for intr in result.interruptions:
                print(f"Tool: {intr.name}, Arguments: {intr.arguments}")
                approved = input("Approve this tool call? (y/n): ").strip().lower() == "y"
                if approved:
                    run_ctx.approve(intr)
                    print(f"✓ Approved {intr.name}")
                else:
                    run_ctx.reject(intr)
                    print(f"✗ Rejected {intr.name}")
            # Resume execution after approvals
            result = await Runner.run(agent, run_ctx)
        
        print("\n--- Final Output ---")
        print(result.final_output)

# -------------------- Run Script --------------------

if __name__ == "__main__":
    """
    What we learn here:
    - Always enforce tool usage (no AI shortcuts) to maintain data accuracy.
    - RunContextWrapper helps track state, approvals, and auditing.
    - Human-in-the-loop allows approvals for sensitive operations.
    - Debug statements help trace control flow and execution timing.
    
    Observations:
    - Direct responses are disallowed, AI must call tools.
    - Approval interruptions are tracked and can be resumed.
    - Timing each agent execution helps monitor performance.
    
    Things to do:
    - Use dynamic inputs for employee names and leave requests.
    - Track approvals for audit logs.
    
    Things to avoid:
    - Returning data directly without tool usage.
    - Skipping human approval for sensitive actions.
    
    Sample Questions to try:
    1. "Check leave balance for Preethi"
       Expected: "Preethi has 0 leave days remaining."
    2. "Request 2 days leave for Pavan Kumar Paishetty"
       Expected: "Leave approved for 2 days. Remaining balance: 3."
    3. "Request 6 days leave for Preethi"
       Expected: "Leave denied. Not enough balance. Current balance: 0."
    """
    asyncio.run(main())