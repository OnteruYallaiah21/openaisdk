import asyncio
import json
from agents import (
    Agent,
    AgentHooks,
    Runner,
    function_tool,
    tool_input_guardrail,
    ToolInputGuardrailData,
    ToolGuardrailFunctionOutput,
)
import sys
import json

from anyio import Path

# Add root path for local imports
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from llm_model_config.llm_model_config import ModelSingleton

# ------------------ MODEL ------------------
model = ModelSingleton.get_instance()

# ------------------ HOOKS ------------------
class DebugHooks(AgentHooks):
    def __init__(self, display_name: str):
        self.display_name = display_name
        self.counter = 0

    async def on_start(self, context, agent):
        self.counter += 1
        print(f"[{self.display_name}] {self.counter}: Agent {agent.name} START → {context.turn_input}")

    async def on_end(self, context, agent, output):
        self.counter += 1
        print(f"[{self.display_name}] {self.counter}: Agent {agent.name} END → {output}")

# ------------------ TOOLS ------------------
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

# ------------------ INPUT GUARDRAIL ------------------
@tool_input_guardrail
def company_input_guardrail(data: ToolInputGuardrailData) -> ToolGuardrailFunctionOutput:
    """Reject inputs that are not company-related."""
    try:
        args = json.loads(data.context.tool_arguments)
        user_input = args.get("input", "")
    except Exception:
        user_input = str(data.context.tool_arguments)

    allowed_keywords = ["dev", "code", "task", "hr", "candidate", "employee",
                        "sales", "pitch", "product", "manager", "approve", "document"]

    if not any(keyword in user_input.lower() for keyword in allowed_keywords):
        return ToolGuardrailFunctionOutput.reject_content(
            message="🚨 Input rejected: Only company-related questions are allowed.",
            output_info={"blocked_input": user_input}
        )
    return ToolGuardrailFunctionOutput(output_info="Input validated")

# ------------------ AGENTS ------------------
dev_agent = Agent(
    name="Dev Agent",
    instructions="You are a Dev agent. Answer only development/project questions.",
    tools=[code_review],
    model=model,
    hooks=DebugHooks("Dev Agent"),
    input_guardrails=[company_input_guardrail],  # attach guardrail correctly
)

hr_agent = Agent(
    name="HR Agent",
    instructions="You are an HR agent. Answer only HR-related company questions.",
    tools=[hr_evaluation],
    model=model,
    hooks=DebugHooks("HR Agent"),
    input_guardrails=[company_input_guardrail],
)

sales_agent = Agent(
    name="Sales Agent",
    instructions="You are a Sales agent. Answer only Sales-related company questions.",
    tools=[sales_pitch],
    model=model,
    hooks=DebugHooks("Sales Agent"),
    input_guardrails=[company_input_guardrail],
)

manager_agent = Agent(
    name="Manager Agent",
    instructions="You are a Manager agent. Answer only Manager-related company questions.",
    tools=[manager_approval],
    model=model,
    hooks=DebugHooks("Manager Agent"),
    input_guardrails=[company_input_guardrail],
)

# ------------------ ROUTING ------------------
async def route_agent(user_input: str) -> Agent:
    user_lower = user_input.lower()
    if "dev" in user_lower or "code" in user_lower or "task" in user_lower:
        return dev_agent
    if "hr" in user_lower or "candidate" in user_lower or "employee" in user_lower:
        return hr_agent
    if "sales" in user_lower or "pitch" in user_lower or "product" in user_lower:
        return sales_agent
    if "manager" in user_lower or "approve" in user_lower or "document" in user_lower:
        return manager_agent
    # default fallback
    return hr_agent

# ------------------ ORCHESTRATOR ------------------
async def company_orchestrator(user_input: str):
    agent = await route_agent(user_input)
    result = await Runner.run(agent, input=user_input)
    return result.final_output

# ------------------ MAIN LOOP ------------------
async def main():
    print("==== High-Level Company Simulator with Guardrails ====")
    while True:
        user_input = input("\nEnter your question (or 'exit' to quit): ").strip()
        if user_input.lower() == "exit":
            break
        output = await company_orchestrator(user_input)
        print(f"\nFinal Output:\n{output}\n")

if __name__ == "__main__":
    asyncio.run(main())