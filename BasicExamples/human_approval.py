import os
from pathlib import Path
rootpath = Path(__file__).resolve().parent.parent
import sys
sys.path.append(str(rootpath))
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()
from typing import Annotated
from pydantic import BaseModel , Field
from agents import Agent, Runner, function_tool


@function_tool(needs_approval=True)
async def cancel_order(order_id: int) -> str:
    return f"Cancelled order {order_id}"


async def requires_review(_ctx, params, _call_id) -> bool:
    return "refund" in params.get("subject", "").lower()


@function_tool(needs_approval=requires_review)
async def send_email(subject: str, body: str) -> str:
    return f"Sent '{subject}'"


agent = Agent(
    name="Support agent",
    instructions="Handle tickets and ask for approval when needed.",
    tools=[cancel_order, send_email],
    model=model,
)

if __name__ == "__main__":
    import asyncio

    async def main():
        print("Testing cancel_order (should require approval)")
        result = await Runner.run(agent, "Please cancel order 12345")
        print(result.final_output)

        print("\nTesting send_email with non-refund subject (should NOT require approval)")
        result = await Runner.run(agent, "Send an email with subject 'Meeting Reminder' and body 'Don't forget our meeting tomorrow!'")
        print(result.final_output)

        print("\nTesting send_email with refund subject (should require approval)")
        result = await Runner.run(agent, "Send an email with subject 'Refund Request' and body 'I want a refund for my last purchase.'")
        print(result.final_output)

    asyncio.run(main())