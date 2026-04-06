import asyncio
import sys
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field

# 1. SETUP MODEL CONFIG
basepath = Path(__file__).resolve().parent.parent
sys.path.append(str(basepath))
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()

from agents import (
    Agent, Runner, RunContextWrapper, AgentHooks, RunHooks,
    AgentHookContext, handoff, function_tool, Tool
)

# --- SCHEMAS FOR SAFETY ---
class HandoffMetadata(BaseModel):
    """Ensures handoffs have a valid JSON schema."""
    reason: str = Field(description="The reason for transferring to this agent")

class SupportState(BaseModel):
    user_name: str = "Yallaiah"
    refund_amount: float = 150.0
    status: str = "INITIALIZING"

# --- GLOBAL RUN HOOKS ---
class GlobalMonitor(RunHooks):
    async def on_agent_start(self, context: AgentHookContext, agent: Agent):
        print(f"\n🌍 [GLOBAL 1] SESSION START: {agent.name}")

    async def on_handoff(self, context: RunContextWrapper, from_agent: Agent, to_agent: Agent):
        print(f"🌍 [GLOBAL 6] 🔄 CROSS-AGENT HANDOFF: {from_agent.name} -> {to_agent.name}")

    async def on_agent_end(self, context: AgentHookContext, agent: Agent, output: Any):
        print(f"🌍 [GLOBAL 7] SESSION END. Status: {context.context.status}")

# --- AGENT SPECIFIC HOOKS ---
class SpecialistHooks(AgentHooks):
    async def on_start(self, context: AgentHookContext, agent: Agent):
        print(f"   👤 [AGENT:{agent.name} 8] Hook Start.")

    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool):
        print(f"   👤 [AGENT:{agent.name} 11] Calling Tool: {tool.name}")

    async def on_handoff(self, context: RunContextWrapper, agent: Agent, source: Agent):
        print(f"   👤 [AGENT:{agent.name} 13] Control received from {source.name}")

    async def on_end(self, context: AgentHookContext, agent: Agent, output: Any):
        print(f"   👤 [AGENT:{agent.name} 14] Hook End.")

# --- TOOLS ---
@function_tool
async def get_customer_loyalty(ctx: RunContextWrapper, confirm: bool = True):
    """
    Retrieves customer loyalty tier.
    Args:
        confirm: Set to True to confirm lookup. (Added to fix OpenAI 400 Schema error)
    """
    print("      ⚙️ [ACTION] Fetching loyalty data...")
    return "Platinum Member (High Priority)"

# --- HANDOFF CALLBACKS ---
async def on_billing_transfer(ctx: RunContextWrapper, input_data: HandoffMetadata):
    print(f"      ⚙️ [LIFECYCLE] Pre-Handoff Billing Logic. Reason: {input_data.reason}")
    ctx.context.status = "BILLING_REVIEW"

async def on_refund_transfer(ctx: RunContextWrapper, input_data: HandoffMetadata):
    print(f"      ⚙️ [LIFECYCLE] Pre-Handoff Refund Logic. Reason: {input_data.reason}")
    ctx.context.status = "REFUND_PROCESSING"

# --- AGENT DEFINITIONS ---
billing_agent = Agent(
    name="Billing_Agent",
    instructions="Process billing queries. Finish by saying 'Billing handled'.",
    model=model,
    hooks=SpecialistHooks()
)

refund_agent = Agent(
    name="Refund_Agent",
    instructions="Process refunds. Finish by saying 'Refund Issued'.",
    model=model,
    hooks=SpecialistHooks()
)

triage_agent = Agent(
    name="Triage_Agent",
    instructions=(
        "1. Check customer loyalty with get_customer_loyalty.\n"
        "2. If refund requested, hand off to Refund_Agent.\n"
        "3. If billing issues, hand off to Billing_Agent."
    ),
    model=model,
    tools=[get_customer_loyalty],
    handoffs=[
        handoff(billing_agent, on_handoff=on_billing_transfer, input_type=HandoffMetadata),
        handoff(refund_agent, on_handoff=on_refund_transfer, input_type=HandoffMetadata)
    ],
    hooks=SpecialistHooks()
)

# --- EXECUTION ---
async def main():
    state = SupportState()
    ctx_wrapper = RunContextWrapper(context=state)
    print(f"🚀 STARTING SCHEMA-SAFE WORKFLOW\n")
    
    await Runner.run(
        triage_agent,
        input="I'm a Platinum member. I need a refund for $150.",
        context=ctx_wrapper,
        hooks=GlobalMonitor()
    )

if __name__ == "__main__":
    asyncio.run(main())