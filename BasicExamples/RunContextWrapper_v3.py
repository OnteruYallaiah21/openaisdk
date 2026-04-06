import asyncio
import sys
import traceback
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List, Any
basepath = Path(__file__).resolve().parent.parent
sys.path.append(str(basepath))
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()
from agents import (
    Agent, Runner, RunContextWrapper, AgentHooks, 
    AgentHookContext, function_tool, Tool, enable_verbose_stdout_logging
)

# 1. SETUP MODEL CONFIG


# 2. THE SHARED DATA MODEL
class OrderState(BaseModel):
    order_id: str
    status: str = "Pending"
    priority: str = "Normal"
    history: List[str] = Field(default_factory=list)

# 3. THE LIFECYCLE MONITOR
class WorkflowTracker(AgentHooks):
    async def on_start(self, context: AgentHookContext, agent: Agent):
        print(f"************ the agent hook context on_start: {context}\n ")
        print(f"the run context wrapper context on_start: { RunContextWrapper}\n ")
        print(f"\n--- [HOOK: START] {agent.name} is now processing the request. ---")


    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool):
        print(f"--- [HOOK: TOOL] {agent.name} is calling {tool.name}... ---")
        print(f"************ the agent hook context on_tool_start: {context}\n ")
        print(f"************the run context wrapper context on_tool_start: { RunContextWrapper}\n ")    
    async def on_handoff(self, context: RunContextWrapper, agent: Agent, source: Agent):
        print(f"--- [HOOK: HANDOFF] {source.name} -> {agent.name} ---")
        print(f"************ the agent hook context on_handoff: {context}\n ")
        print(f"************the run context wrapper context on_handoff: { RunContextWrapper}\n ")
    async def on_end(self, context: RunContextWrapper, agent: Agent, output: Any):
        state = context.context 
        print(f"--- [HOOK: END] {agent.name} finished. Final Status: {state.status} ---")
        print(f"************* the agent hook context on_end: {context}\n ")
        print(f"************ the run context wrapper context on_end: { RunContextWrapper}\n ")   
# 4. THE TOOLS
@function_tool
async def check_warehouse_db(ctx: RunContextWrapper, order_id: str):
    """
    Checks the physical warehouse for order location.
    Args:
        order_id: The ID of the order to look up.
    """
    state = ctx.context
    state.status = "Delayed (Backlog)"
    state.priority = "High"
    state.history.append(f"Warehouse DB: Checked {order_id}. Item in Aisle 9.")
    return {"location": "Aisle 9", "status": "Paused"}

# 5. THE AGENTS
shipping_specialist = Agent(
    name="Shipping_Specialist",
    instructions="Review the warehouse notes provided in the context and explain the delay kindly.",
    model=model,
    hooks=WorkflowTracker()
)

# MANUAL HANDOFF TOOL: This solves the OpenAI Schema 400 error
@function_tool
async def transfer_to_shipping_specialist(ctx: RunContextWrapper, reason: str = "Escalation"):
    """
    Transfer the conversation to a Shipping Specialist.
    Args:
        reason: The reason for the transfer.
    """
    # This manually triggers the handoff mechanism 
    # while providing a 'reason' property to keep the JSON schema valid.
    return shipping_specialist

triage_agent = Agent(
    name="Triage_Agent",
    instructions=(
        "1. Use 'check_warehouse_db' to see order status. "
        "2. If the status is Delayed, use 'transfer_to_shipping_specialist' immediately."
    ),
    tools=[transfer_to_shipping_specialist,check_warehouse_db],
    model=model,
    hooks=WorkflowTracker()
)

# 6. MAIN EXECUTION
async def main():
    enable_verbose_stdout_logging()
    
    initial_state = OrderState(order_id="ORD-2026")
    ctx_wrapper = RunContextWrapper(context=initial_state)
    print(f"*********** The RunContextWrapper context in main function before calling the Runner after intilized with pydantic model: {ctx_wrapper}\n and context.context: {ctx_wrapper.context}\n ")
    print("=== STARTING REAL-TIME WORKFLOW ===")
    
    try:
        response = await Runner.run(
            triage_agent,
            input="Where is my order ORD-2026?",
            context=ctx_wrapper
        )

        print("\n" + "="*50)
        print("FINAL AGENT RESPONSE:")
        output = getattr(response, 'final_output', getattr(response, 'content', 'No output found'))
        print(output)
        print("="*50)

        print("\n--- POST-RUN STATE AUDIT ---")
        print(f"Final Status:  {initial_state.status}")
        print(f"Final History: {initial_state.history}")

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

    """
    tracing:
    agent 1
    1.tool->check_warehouse_db,2
    """