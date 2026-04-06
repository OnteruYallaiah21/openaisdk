import asyncio
from pathlib import Path
from agents import Agent,Runner, ModelSettings
import sys
import os
rootpath= Path(__file__).resolve().parent.parent
sys.path.append(str(rootpath))
from llm_model_config.llm_model_config import ModelSingleton
groq_model = ModelSingleton.get_instance()

async def main():
    print("inside main def function")
    model_agnet = Agent(
        name = "Farmwers Helpful assistant",
        instructions= "you are helpful assistant for farmer to hel and guid in cutivation process for indian farmers",
        model= groq_model,
    )
    result = await Runner.run(model_agnet, "what is the best cultivation crop for the people of praksam district especially pullalchervu lands ")
    print(result.final_output)      

if __name__ == "__main__":
    print(f"I am inside file called => {Path(__file__).resolve()}")
    asyncio.run(main())