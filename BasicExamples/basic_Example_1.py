import asyncio
from pathlib import Path
import sys
path = Path(__file__).resolve().parent.parent
sys.path.append(str(path))
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()
from agents import Agent, Runner

async def main():
    myfirstagnet = Agent(
        name = "Farmer Agnet",
        instructions= "you are helpful assistant for farmer to hel and guid in cutivation process for indian farmers",
        model=model,
    )
    result = await Runner.run(myfirstagnet, "what is the best cultivation crop for the people of praksam district especially pullalchervu lands ")
    print(result.final_output)
if __name__ == "__main__":
    print(f"I am inside file called => {Path(__file__).resolve()}")
    print("hellow world")
    asyncio.run(main())