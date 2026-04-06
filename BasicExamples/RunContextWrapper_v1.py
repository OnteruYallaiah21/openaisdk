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

# 3. DEFINE GUARDRAILS (Fixed with output_info)
@input_guardrail(run_in_parallel=True)
async def pii_shield(ctx: RunContextWrapper, agent, input_text):
    print(f"\n[GUARDRAIL] Scanning input: {input_text[:50]}...")
    return GuardrailFunctionOutput(
        tripwire_triggered=False, 
        output_info={"scan_status": "passed"}
    )

# 4. DEFINE TOOLS (With explicit Error Handling to prevent loops)
@function_tool
async def get_order_details(ctx: RunContextWrapper, order_id: str):
    """
    Fetches the current status of an order from the database.
    Args:
        order_id: The ID of the order (e.g., ORD-99)
    """
    print(f"\n[TOOL: DB] Executing lookup for: {order_id}")
    
    try:
        # ACCESS LOGIC: Directly access the 'context' attribute of the wrapper
        # Based on your logs, ctx.context is the SupportContext instance.
        support_ctx = ctx.context
        
        print(f"*********** The SupportContext inside tool: {support_ctx}")

        # Real-time state mutation
        # This updates the original object created in your main() function
        support_ctx.order_status = "Delayed"
        support_ctx.priority_level = "High"
        support_ctx.internal_audit_log.append(f"Order {order_id} marked Delayed via Tool.")
        
        print(f"DEBUG: Context successfully updated in real-time.")

        return {
            "order_id": order_id,
            "status": "Delayed",
            "eta": "2026-04-15",
            "reason": "Logistics backlog"
        }
    except Exception as e:
        print(f"TOOL ERROR: {e}")
        # Printing the directory of ctx to see available methods/attributes if it fails again
        print(f"Available attributes in ctx: {dir(ctx)}")
        return {"error": str(e)}

# 5. DEFINE THE AGENT
triage_agent = Agent(
    name="Triage Agent",
    instructions=(
        "You are a helpful support agent. When a user asks about an order, "
        "use the 'get_order_details' tool. Once you have the status, "
        "explain the situation clearly to the user."
    ),
    tools=[get_order_details],
    model=model,
    input_guardrails=[pii_shield]
)

# 6. MAIN EXECUTION
async def main():
    # Enable logs so we can see the 'Calling LLM' and 'Invoking tool' steps
    enable_verbose_stdout_logging()
    
    print("--- STARTING AGENTIC WORKFLOW ---")

    # A: Create the actual data object
    my_data = SupportContext(user_id="Yallaiah_Onteru")
    
    # B: Put that data into the Wrapper
    # This is critical: The wrapper 'holds' the model so tools can find it
    ctx_wrapper = RunContextWrapper(context=my_data)
    print(f"*********** The RunContextWrapper context in main function: {ctx_wrapper}\n and context.context: {ctx_wrapper.context}\n ")
    print(f"Initial Context: {my_data.model_dump()}\n")

    user_query = "Where is my order #ORD-99? I'm getting worried!"

    try:
        # C: Run the agent using the 'context' parameter for the wrapper
        response = await Runner.run(
            triage_agent, 
            user_query, 
            context=ctx_wrapper 
        )

        print("\n" + "="*50)
        print("FINAL AGENT RESPONSE TO USER:")
        print(response.final_output)
        print("="*50)

        # D: Verify that the local 'my_data' object was updated by the Agent's tool
        print("\n--- POST-RUN STATE AUDIT ---")
        print(f"User ID:        {my_data.user_id}")
        print(f"Order Status:   {my_data.order_status}")
        print(f"Priority Level: {my_data.priority_level}")
        print(f"Internal Logs:  {my_data.internal_audit_log}")

    except Exception as e:
        print(f"Workflow Exception: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())