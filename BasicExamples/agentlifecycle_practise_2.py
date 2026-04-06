import asyncio
import random
from typing import Any, Optional
from datetime import datetime

from pydantic import BaseModel

from agents import (
    Agent,
    AgentHookContext,
    AgentHooks,
    RunContextWrapper,
    Runner,
    Tool,
    function_tool,
)
import os
import sys
from pathlib import Path    
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))
from llm_model_config.llm_model_config import ModelSingleton

model = ModelSingleton.get_instance()


import asyncio
from typing import Any
import random

from agents import Agent, AgentHooks, Runner, Tool, function_tool, RunContextWrapper, AgentHookContext

# ================= HOOKS =================
class CustomAgentHooks(AgentHooks):
    def __init__(self, display_name: str):
        self.event_counter = 0
        self.display_name = display_name

    async def on_start(self, context: AgentHookContext, agent: Agent) -> None:
        self.event_counter += 1
        print(f"[{self.display_name}] {self.event_counter}: Agent {agent.name} started with input: {context.turn_input}")

    async def on_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        self.event_counter += 1
        print(f"[{self.display_name}] {self.event_counter}: Agent {agent.name} ended with output: {output}")

    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool) -> None:
        self.event_counter += 1
        print(f"[{self.display_name}] {self.event_counter}: Agent {agent.name} started tool {tool.name}")

    async def on_tool_end(self, context: RunContextWrapper, agent: Agent, tool: Tool, result: str) -> None:
        self.event_counter += 1
        print(f"[{self.display_name}] {self.event_counter}: Agent {agent.name} ended tool {tool.name} with result: {result}")


# ================= TOOLS =================
@function_tool
def code_review(task: str) -> str:
    return f"Dev team reviewed task: '{task}'."

@function_tool
def hr_evaluation(candidate_name: str) -> str:
    return f"HR evaluated candidate '{candidate_name}' successfully."

@function_tool
def sales_pitch(product: str) -> str:
    return f"Sales pitch prepared for product '{product}'."

@function_tool
def manager_approval(document: str) -> str:
    return f"Manager approved document '{document}'."

@function_tool
def ceo_decision(report: str) -> str:
    return f"CEO reviewed report '{report}' and made strategic decision."


# ================= MODEL =================
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()


# ================= AGENTS =================
dev_agent = Agent(
    name="Dev Agent",
    instructions="Perform dev tasks using code_review tool.",
    tools=[code_review],
    model=model,
    hooks=CustomAgentHooks("Dev Agent")
)

hr_agent = Agent(
    name="HR Agent",
    instructions="Perform HR evaluation using hr_evaluation tool.",
    tools=[hr_evaluation],
    model=model,
    hooks=CustomAgentHooks("HR Agent")
)

sales_agent = Agent(
    name="Sales Agent",
    instructions="Perform sales tasks using sales_pitch tool.",
    tools=[sales_pitch],
    model=model,
    hooks=CustomAgentHooks("Sales Agent")
)

manager_agent = Agent(
    name="Manager Agent",
    instructions="Approve documents using manager_approval tool.",
    tools=[manager_approval],
    model=model,
    hooks=CustomAgentHooks("Manager Agent")
)

ceo_agent = Agent(
    name="CEO Agent",
    instructions="Make strategic decision using ceo_decision tool.",
    tools=[ceo_decision],
    model=model,
    hooks=CustomAgentHooks("CEO Agent")
)


# ================= ORCHESTRATOR =================
async def company_orchestrator(user_question: str):
    print(f"\nUser Question: {user_question}\n")

    q_lower = user_question.lower()

    if any(word in q_lower for word in ["bug", "feature", "code"]):
        result = await Runner.run(dev_agent, input=user_question)
    elif any(word in q_lower for word in ["candidate", "resume", "interview"]):
        result = await Runner.run(hr_agent, input=user_question)
    elif any(word in q_lower for word in ["client", "pitch", "sales", "product"]):
        result = await Runner.run(sales_agent, input=user_question)
    elif any(word in q_lower for word in ["approval", "document", "report"]):
        result = await Runner.run(manager_agent, input=user_question)
    elif any(word in q_lower for word in ["strategy", "decision", "ceo"]):
        result = await Runner.run(ceo_agent, input=user_question)
    else:
        # Fallback
        result = await Runner.run(manager_agent, input=user_question)

    print(f"\nAgent Output: {result.final_output}\n")
    return result.final_output


# ================= MAIN =================
async def main():
    questions = [
        "Fix the login bug in the app",
        "Evaluate candidate John Doe",
        "Prepare pitch for new product launch",
        "Approve the quarterly sales report",
        "CEO needs to make a strategic decision"
    ]

    for q in questions:
        print("="*60)
        await company_orchestrator(q)
        print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())