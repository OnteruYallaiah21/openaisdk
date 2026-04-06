import asyncio
from typing import Any, Dict, Optional
from pydantic import BaseModel
from datetime import datetime
import os
import sys
from pathlib import Path    
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))
from agents import Agent, AgentHooks, Runner, Tool, function_tool, RunContextWrapper, AgentHookContext
from llm_model_config.llm_model_config import ModelSingleton

model = ModelSingleton.get_instance()



# ====================== HOOKS ======================
class DebugAgentHooks(AgentHooks):
    """Custom hooks for debugging and tracing agent/tool execution."""

    def __init__(self, display_name: str):
        self.display_name = display_name
        self.counter = 0

    async def on_start(self, context: AgentHookContext, agent: Agent) -> None:
        self.counter += 1
        print(f"[{self.display_name}] {self.counter}: Agent {agent.name} START → {context.turn_input}")

    async def on_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        self.counter += 1
        print(f"[{self.display_name}] {self.counter}: Agent {agent.name} END → {output}")

    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool) -> None:
        self.counter += 1
        print(f"[{self.display_name}] {self.counter}: Agent {agent.name} TOOL START → {tool.name}")

    async def on_tool_end(self, context: RunContextWrapper, agent: Agent, tool: Tool, result: str) -> None:
        self.counter += 1
        print(f"[{self.display_name}] {self.counter}: Agent {agent.name} TOOL END → {tool.name} = {result}")


# ====================== TOOLS ======================
@function_tool
def code_review(task: str) -> str:
    """ Simulate a dev team code review."""
    return f"Dev team reviewed task: '{task}'."


@function_tool
def hr_evaluation(candidate_name: str) -> str:
    """ Simulate HR evaluation of a candidate."""
    return f"HR evaluated candidate '{candidate_name}' successfully."


@function_tool
def sales_pitch(product: str) -> str:
    """ Simulate Sales pitch preparation."""
    return f"Sales pitch prepared for product '{product}'."


@function_tool
def manager_approval(document: str) -> str:
    """ Simulate Manager document approval. """
    return f"Manager approved document '{document}'."


@function_tool
def ceo_decision(report: str) -> str:
    """Simulate CEO decision-making on a report."""
    return f"CEO reviewed report '{report}' and made strategic decision."


# ====================== AGENTS ======================
# Define agents with tools, hooks, and instructions
dev_agent = Agent(
    name="Dev Agent",
    instructions="Perform development tasks using code_review tool.",
    tools=[code_review],
    model=model,
    hooks=DebugAgentHooks("Dev Agent"),
)

hr_agent = Agent(
    name="HR Agent",
    instructions="Perform HR evaluation using hr_evaluation tool.",
    tools=[hr_evaluation],
    model=model,
    hooks=DebugAgentHooks("HR Agent"),
)

sales_agent = Agent(
    name="Sales Agent",
    instructions="Perform sales tasks using sales_pitch tool.",
    tools=[sales_pitch],
    model=model,
    hooks=DebugAgentHooks("Sales Agent"),
)

manager_agent = Agent(
    name="Manager Agent",
    instructions="Approve documents using manager_approval tool.",
    tools=[manager_approval],
    model=model,
    hooks=DebugAgentHooks("Manager Agent"),
)

ceo_agent = Agent(
    name="CEO Agent",
    instructions="Make strategic decisions using ceo_decision tool.",
    tools=[ceo_decision],
    model=model,
    hooks=DebugAgentHooks("CEO Agent"),
)


# ====================== ROUTING MODEL ======================
class RoutingRequest(BaseModel):
    """Model for structured routing request."""
    user_question: str
    suggested_agent: Optional[str] = None


async def dynamic_routing(user_question: str) -> Agent:
    """
    Dynamically determine which agent should handle a user question.
    Uses the LLM itself to decide routing based on input context.
    """
    routing_prompt = f"""
    You are a smart assistant that routes tasks to the correct department.
    User asked: "{user_question}"
    Respond ONLY with one of: Dev, HR, Sales, Manager, CEO.
    """

    # Call the LLM via a temporary agent for routing
    routing_agent = Agent(
        name="Router Agent",
        instructions=routing_prompt,
        model=model,
    )

    routing_result = await Runner.run(routing_agent, input=user_question)
    suggested_agent = routing_result.final_output.strip().lower()
    
    print(f"[DEBUG-Routing] Routing Model Suggestion: {suggested_agent}")

    agent_map = {
        "dev": dev_agent,
        "hr": hr_agent,
        "sales": sales_agent,
        "manager": manager_agent,
        "ceo": ceo_agent,
    }

    return agent_map.get(suggested_agent, manager_agent)  # fallback to manager


# ====================== ORCHESTRATOR ======================
async def company_orchestrator(user_question: str) -> str:
    """Orchestrate the full company workflow based on user question."""
    print(f"\nUser Input: {user_question}\n")

    # Step 1: Determine which agent should handle the question dynamically
    agent = await dynamic_routing(user_question)
    print(f"Routing → Selected Agent: {agent.name}")

    # Step 2: Run the selected agent with full context
    result = await Runner.run(agent, input=user_question)

    print(f"\nFinal Agent Output: {result.final_output}\n")
    return result.final_output


# ====================== MAIN ======================
async def main():
    print("==== Interactive Company Simulator ====")
    while True:
        user_input = input("\nEnter your question (or 'exit' to quit): ").strip()
        if user_input.lower() == "exit":
            break
        await company_orchestrator(user_input)


if __name__ == "__main__":
    asyncio.run(main())