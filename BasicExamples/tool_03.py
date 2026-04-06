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

class villagedetails(BaseModel):
    village_name: str = Field(description="Name of the village")
    temparture: float = Field(description="current temperature of the village")
    conditions: str = Field(description="Current weather conditions of the village")  

@function_tool
def get_village_weather(village_name: str) -> dict:
    print(f"Getting weather details for village: {village_name}")
    
    return {
        "village_name": village_name,
        "temperature": 30.0,
        "condition": "Sunny",
        "humidity": 60,
    }

agent = Agent (
    name="Village Weather Agent",
    instructions="You provide weather details for villages.",
    model=model,
    tools=[get_village_weather]
)

async def main():
    result = await Runner.run(agent, "What is the current weather in Pullalchervu?")
    print(result.final_output)      
 



if __name__ == "__main__":    
    print(f"I am inside file called => {Path(__file__).resolve()}")
    import asyncio
    asyncio.run(main())  