import asyncio
from pathlib import Path
import sys

# Add project root to path so we can import llm_model_config
sys.path.append(str(Path(__file__).parent.parent))

from llm_model_config.llm_model_config import ModelSingleton
from agents import Agent, Runner, function_tool

# --- Function tools ---
@function_tool
def history_fun_fact() -> str:
    """Return a short history fact."""
    return "Sharks are older than trees."

@function_tool
def math_fun_fact() -> str:
    """Return a short math fact."""
    return "Zero is the only number that is neither negative nor positive."

# --- Singleton model instance ---
model = ModelSingleton.get_instance()
if model is None:
    raise RuntimeError("LLM model failed to initialize!")

# --- Specialist agents ---
history_tutor_agent = Agent(
    name="History Tutor",
    instructions="You answer history questions clearly and concisely.",
    tools=[history_fun_fact],
    model=model
)

math_tutor_agent = Agent(
    name="Math Tutor",
    instructions="You explain math step by step and include worked examples.",
    tools=[math_fun_fact],
    model=model
)

# --- Triage agent (orchestrator) ---
triage_agent = Agent(
    name="Triage Agent",
    instructions="Route each homework question to the right specialist agent.",
    handoffs=[history_tutor_agent, math_tutor_agent],
    model=model,
   
)

# --- Async runner ---
async def main():
    queries = [
        "Who was the first president of the United States?",
        "Tell me something surprising about ancient life on Earth.",
        "Give me a fun fact about numbers."
    ]

    for q in queries:
        result = await Runner.run(triage_agent, input=q)
        print(f"Query: {q}")
        print(f"Answer: {result.final_output}")
        print(f"Answered by: {result.last_agent.name}\n")


if __name__ == "__main__":
    asyncio.run(main())