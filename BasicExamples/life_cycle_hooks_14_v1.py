import asyncio
import sys
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel

# 1. SETUP MODEL CONFIG
basepath = Path(__file__).resolve().parent.parent
sys.path.append(str(basepath))
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()

from agents import (
    Agent, Runner, RunContextWrapper, AgentHooks, RunHooks,
    AgentHookContext, function_tool, Tool
)

# --- SHARED BUSINESS STATE ---
class SupportState(BaseModel):
    user_name: str = "Yallaiah"
    refund_amount: float = 150.0 
    status: str = "IN_PROGRESS"

# --- GLOBAL RUN HOOKS ---
class GlobalMonitor(RunHooks):
    async def on_agent_start(self, context: AgentHookContext, agent: Agent):
        print(f"\n🌍 [GLOBAL HOOK: 1] SYSTEM STARTING SESSION\nTarget: {agent.name}")

    async def on_handoff(self, context: RunContextWrapper, from_agent: Agent, to_agent: Agent):
        print(f"\n🌍 [GLOBAL HOOK: 6] 🔄 SYSTEM-WIDE HANDOFF: {from_agent.name} -> {to_agent.name}")

    async def on_agent_end(self, context: AgentHookContext, agent: Agent, output: Any):
        print(f"\n🌍 [GLOBAL HOOK: 7] SYSTEM SESSION COMPLETE\nFinal Status: {context.context.status}")

# --- AGENT SPECIFIC HOOKS ---
class SpecialistHooks(AgentHooks):
    async def on_start(self, context: AgentHookContext, agent: Agent):
        print(f"--- [👤 HOOK: START] {agent.name} active. ---")

    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool):
        print(f"\n--- [👤 HOOK: TOOL] {agent.name} calling {tool.name}... ---")

    async def on_handoff(self, context: RunContextWrapper, agent: Agent, source: Agent):
        print(f"\n--- [👤 HOOK: HANDOFF] {source.name} -> {agent.name} ---")

    async def on_end(self, context: AgentHookContext, agent: Agent, output: Any):
        print(f"\n--- [👤 HOOK: END] {agent.name} finished. ---")

# --- BUSINESS LOGIC / TOOL ---
@function_tool
async def transfer_to_manager(ctx: RunContextWrapper, reason: str):
    """
    Transfer to a manager for high-value refunds.
    Args:
        reason: The reason for escalation (Required to ensure valid JSON schema).
    """
    print(f"\n      ⚙️ [LOGIC] Escalating to Manager. Reason: {reason}")
    ctx.context.status = "ESCALATED"
    return manager_agent

# --- AGENTS ---
manager_agent = Agent(
    name="Manager_Agent",
    instructions="You are the Refund Manager. Approve the refund and say 'Refund complete'.",
    model=model,
    hooks=SpecialistHooks()
)

triage_agent = Agent(
    name="Triage_Agent",
    instructions="If refund_amount > 100, use transfer_to_manager and provide a reason.",
    model=model,
    tools=[transfer_to_manager], # Use the explicit tool instead of handoffs=[]
    hooks=SpecialistHooks()
)

# --- MAIN ---
async def main():
    state = SupportState(refund_amount=150.0) 
    ctx_wrapper = RunContextWrapper(context=state)
    
    print(f"🚀 STARTING 14-HOOK DEBUG TRACE (Refund: ${state.refund_amount})\n")
    
    await Runner.run(
        triage_agent,
        input="I need a refund for my $150 order.",
        context=ctx_wrapper,
        hooks=GlobalMonitor()
    )

if __name__ == "__main__":
    asyncio.run(main())