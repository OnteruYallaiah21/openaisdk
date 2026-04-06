import asyncio
from typing import Any, Optional
from pydantic import BaseModel
from pathlib import Path
import sys

# Add root path for local imports
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from agents import (
    Agent,
    AgentHooks,
    Runner,
    function_tool,
    RunContextWrapper,
    AgentHookContext,
    ToolInputGuardrailData,
    ToolOutputGuardrailData,
    ToolGuardrailFunctionOutput,
    ToolOutputGuardrailTripwireTriggered,
    tool_input_guardrail,
    tool_output_guardrail,
)
from llm_model_config.llm_model_config import ModelSingleton

model = ModelSingleton.get_instance()


# ====================== DEBUG HOOKS ======================
class DebugAgentHooks(AgentHooks):
    def __init__(self, display_name: str):
        self.display_name = display_name
        self.counter = 0

    async def on_start(self, context: AgentHookContext, agent: Agent) -> None:
        self.counter += 1
        print(f"[{self.display_name}] {self.counter}: Agent {agent.name} START → {context.turn_input}")

    async def on_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        self.counter += 1
        print(f"[{self.display_name}] {self.counter}: Agent {agent.name} END → {output}")


# ====================== TOOLS ======================
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


# ====================== DYNAMIC GUARDRAILS ======================
@tool_input_guardrail
def enforce_input_guardrail(data: ToolInputGuardrailData) -> ToolGuardrailFunctionOutput:
    """
    Dynamically check input for inappropriate requests or unsafe content.
    """
    user_input = data.context.tool_arguments or ""

    # Example dynamic rules: these can later be AI/ML-based checks
    unsafe_indicators = [
        "personal relationship request",
        "sensitive personal info",
        "illegal activity",
        "dating",
        "find girl",
    ]

    for rule in unsafe_indicators:
        if rule.lower() in user_input.lower():
            return ToolGuardrailFunctionOutput.reject_content(
                message=f"🚨 Input blocked: violates company guardrails ({rule})",
                output_info={"input": user_input, "blocked_rule": rule},
            )

    return ToolGuardrailFunctionOutput(output_info="Input validated")


@tool_output_guardrail
def enforce_output_guardrail(data: ToolOutputGuardrailData) -> ToolGuardrailFunctionOutput:
    """
    Dynamically block outputs that contain unsafe instructions or prohibited content.
    """
    output_text = str(data.output)

    unsafe_output_indicators = [
        "personal relationship advice",
        "meet a girl",
        "dating site",
        "illegal activity",
    ]

    for phrase in unsafe_output_indicators:
        if phrase.lower() in output_text.lower():
            return ToolGuardrailFunctionOutput.reject_content(
                message=f"🚨 Output blocked: violates company guardrails ({phrase})",
                output_info={"output": output_text, "blocked_phrase": phrase},
            )

    return ToolGuardrailFunctionOutput(output_info="Output validated")


# ====================== AGENTS ======================
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

# Attach dynamic guardrails to all agents
for agent_obj in [dev_agent, hr_agent, sales_agent, manager_agent, ceo_agent]:
    agent_obj.tool_input_guardrails = [enforce_input_guardrail]
    agent_obj.tool_output_guardrails = [enforce_output_guardrail]


# ====================== DYNAMIC ROUTING ======================
class RoutingRequest(BaseModel):
    user_question: str
    suggested_agent: Optional[str] = None


async def dynamic_routing(user_question: str) -> Agent:
    routing_prompt = f"""
    You are a smart assistant that routes tasks to the correct department.
    User asked: "{user_question}"
    Respond ONLY with one of: Dev, HR, Sales, Manager, CEO.
    """

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
    return agent_map.get(suggested_agent, manager_agent)


# ====================== ORCHESTRATOR ======================
async def company_orchestrator(user_question: str) -> str:
    print(f"\nUser Input: {user_question}\n")
    try:
        agent = await dynamic_routing(user_question)
        print(f"Routing → Selected Agent: {agent.name}")
        result = await Runner.run(agent, input=user_question)
        return result.final_output
    except ToolOutputGuardrailTripwireTriggered as e:
        return f"🚨 Guardrail triggered. Cannot process request: {e.output.output_info}"
    except Exception as e:
        return f"❌ Error: {str(e)}"


# ====================== MAIN LOOP ======================
async def main():
    print("==== Interactive Company Simulator with Dynamic Guardrails ====")
    while True:
        user_input = input("\nEnter your question (or 'exit' to quit): ").strip()
        if user_input.lower() == "exit":
            break
        output = await company_orchestrator(user_input)
        print(f"\nFinal Output:\n{output}\n")


if __name__ == "__main__":
    asyncio.run(main())