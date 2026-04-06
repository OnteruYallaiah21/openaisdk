import asyncio
import sys
import traceback
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List

from agents import (
    Agent, Runner, GuardrailFunctionOutput, 
    input_guardrail, function_tool, RunContextWrapper,
    InputGuardrailTripwireTriggered, enable_verbose_stdout_logging
)

# 1. SETUP MODEL CONFIG
basepath = Path(__file__).resolve().parent.parent
sys.path.append(str(basepath))
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()

# 2. DEFINE SHARED CONTEXT
class SupportContext(BaseModel):
    user_id: str = "USER_123"
    order_status: Optional[str] = "Unknown"
    priority_level: str = "Standard"
    internal_audit_log: List[str] = Field(default_factory=list)

# 3. DEFINE GUARDRAILS
@input_guardrail(run_in_parallel=True)
async def pii_shield(ctx: RunContextWrapper, agent, input_text):
    print(f"\n[GUARDRAIL] Scanning input: {input_text[:50]}...")
    return GuardrailFunctionOutput(
        tripwire_triggered=False, 
        output_info={"scan_status": "passed"}
    )

# 4. DEFINE TOOLS
@function_tool
async def get_order_details(ctx: RunContextWrapper, order_id: str):
    """
    Fetches the current status of an order from the database.
    Args:
        order_id: The ID of the order (e.g., ORD-99)
    """
    print(f"\n[TOOL: DB] Executing lookup for: {order_id}")
    try:
        support_ctx = ctx.context
        # Real-time state mutation
        support_ctx.order_status = "Delayed"
        support_ctx.priority_level = "High"
        support_ctx.internal_audit_log.append(f"Order {order_id} marked Delayed via DB tool.")
        
        return {
            "order_id": order_id,
            "status": "Delayed",
            "eta": "2026-04-15",
            "reason": "Logistics backlog"
        }
    except Exception as e:
        print(f"TOOL ERROR (DB): {e}")
        return {"error": str(e)}

@function_tool
async def inform_warehouse(ctx: RunContextWrapper, order_id: str, priority_note: str):
    """
    Informs the warehouse team about a specific order issue.
    Args:
        order_id: The ID of the order to escalate.
        priority_note: A short note describing the urgency.
    """
    print(f"\n[TOOL: WAREHOUSE] Sending alert for {order_id}...")
    try:
        support_ctx = ctx.context
        
        # Log the escalation in our shared context
        log_entry = f"Warehouse Alert Sent: '{priority_note}' (Current Status: {support_ctx.order_status})"
        support_ctx.internal_audit_log.append(log_entry)
        
        return {
            "warehouse_ticket_id": "TKT-778899",
            "notification_sent": True,
            "current_priority": support_ctx.priority_level
        }
    except Exception as e:
        print(f"TOOL ERROR (WAREHOUSE): {e}")
        return {"error": str(e)}

# 5. DEFINE THE AGENT
triage_agent = Agent(
    name="Triage Agent",
    instructions=(
        "You are a helpful support agent. "
        "1. First, check order status using 'get_order_details'. "
        "2. If the status is 'Delayed', you MUST call 'inform_warehouse' to alert the team. "
        "3. Finally, explain everything to the user with empathy."
    ),
    tools=[get_order_details, inform_warehouse],
    model=model,
    input_guardrails=[pii_shield]
)

# 6. MAIN EXECUTION
async def main():
    enable_verbose_stdout_logging()
    print("--- STARTING COMPLEX WORKFLOW ---")

    # Initialize the actual data object
    my_data = SupportContext(user_id="Yallaiah_Onteru")
    
    # Wrap it for the Runner
    ctx_wrapper = RunContextWrapper(context=my_data)

    user_query = "Where is my order #ORD-99? I'm getting worried!"

    try:
        # Run the agent
        response = await Runner.run(
            triage_agent, 
            user_query, 
            context=ctx_wrapper 
        )
        support_ctx = ctx_wrapper.context
        support_ctx.internal_audit_log.append(response.final_output)
        
        print(f"*********** The RunContextWrapper  after runner context in main function: {ctx_wrapper}\n and context.context: {ctx_wrapper.context}\n ")
        print("\n" + "="*50)
        print("FINAL AGENT RESPONSE TO USER:")
        print(response.final_output) # or response.final_output depending on your SDK version
        print("="*50)

        # D: Verify the Audit Log was updated by BOTH tools
        print("\n--- POST-RUN STATE AUDIT ---")
        print(f"User ID:        {my_data.user_id}")
        print(f"Order Status:   {my_data.order_status}")
        print(f"Priority Level: {my_data.priority_level}")
        print(f"Internal Logs:")
        for log in my_data.internal_audit_log:
            print(f"  - {log}")

    except Exception as e:
        print(f"Workflow Exception: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())