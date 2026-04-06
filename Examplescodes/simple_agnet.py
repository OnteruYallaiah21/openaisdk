import asyncio
from pathlib import Path
import sys
import asyncio

from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()
# above is the recommended way to get the model instance, ensuring it's a singleton and properly initialized.
from agents import Agent, Runner


# Get singleton model instance


agent = Agent(
    name="History Tutor",
    instructions="You answer history questions clearly and concisely.",
    model=model
)

async def main():
    result = await Runner.run(agent, "When did the Roman Empire fall?")
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())