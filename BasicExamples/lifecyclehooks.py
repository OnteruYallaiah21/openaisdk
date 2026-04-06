import asyncio
from pathlib  import Path
from random import random
import sys
rootpath = Path(__file__).resolve().parent.parent
sys.path.append(str(rootpath))
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()
from agents import (Agent, AgentHookContext, Runner, AgentHooks, RunHooks, function_tool,Tool , RunContextWrapper)
from Examplescodes.auto_mode import input_with_fallback, confirm_with_fallback, is_auto_mode
from typing import Any
from pydantic import BaseModel
class CustomAgentHooks(AgentHooks):
    def __init__(self,display_name:str):
        self.display_name = display_name
        self.event_counter = 0
    async def on_start(self, context:AgentHookContext, agent:Agent ):
        self.event_counter+=1
        print(f"[{self.display_name}] Agent is starting. Event count: {self.event_counter}:context: {context}: agent: {agent.name}:started with turn_input: {context.turn_input}")

    async def on_end(self, context:RunContextWrapper, agent:Agent, output:any):
        self.event_counter+=1
        print(f"[{self.display_name}] Agent has ended. Event count: {self.event_counter}:context: {context}: agent: {agent.name}:ended with output: {output}")
    async def on_handoff(self, context: RunContextWrapper, agent: Agent, source: Agent) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {source.name} handed off to {agent.name}"
        )
    # Note: The on_tool_start and on_tool_end hooks apply only to local tools.
    # They do not include hosted tools that run on the OpenAI server side,
    # such as WebSearchTool, FileSearchTool, CodeInterpreterTool, HostedMCPTool,
    # or other built-in hosted tools.
    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {agent.name} started tool {tool.name}"
        )

    async def on_tool_end(
        self, context: RunContextWrapper, agent: Agent, tool: Tool, result: str
    ) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {agent.name} ended tool {tool.name} with result {result}"
        )
@function_tool
def random_number(max: int) -> int:
        """
        Generate a random number from 0 to max (inclusive).
        """
        if is_auto_mode():
            if max <= 0:
                print("[debug] auto mode returning deterministic value 0")
                return 0
            value = min(max, 37)
            if value % 2 == 0:
                value = value - 1 if value > 1 else 1
            print(f"[debug] auto mode returning deterministic odd number {value}")
            return value
        return random.randint(0, max)


@function_tool
def multiply_by_two(x: int) -> int:
    """Simple multiplication by two."""
    return x * 2


class FinalResult(BaseModel):
    number: int


multiply_agent = Agent(
    name="Multiply Agent",
    instructions="Multiply the number by 2 and then return the final result.",
    model=model,
    tools=[multiply_by_two],
    hooks=CustomAgentHooks(display_name="Multiply Agent"),
)

start_agent = Agent(
    name="Start Agent",
    instructions="Generate a random number. If it's even, stop. If it's odd, hand off to the multiply agent.",
    model=model,
    tools=[random_number],
    hooks=CustomAgentHooks(display_name="Start Agent"),
    handoffs=[multiply_agent],
)


async def main() -> None:
    user_input = input_with_fallback("Enter a max number: ", "50")
    try:
        max_number = int(user_input)
        await Runner.run(
            start_agent,
            input=f"Generate a random number between 0 and {max_number}.",
        )
    except ValueError:
        print("Please enter a valid integer.")
        return

    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())