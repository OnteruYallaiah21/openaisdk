import sys
import os
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Annotated
from agents import (Agent, Runner,GuardrailFunctionOutput,
                    input_guardrail,output_guardrail,ToolInputGuardrailData,ToolOutputGuardrailData,ToolOutputGuardrailTripwireTriggered,function_tool,
                    RunContextWrapper,  TResponseInputItem,InputGuardrailTripwireTriggered)
basepath= Path(__file__).resolve().parent.parent
sys.path.append(str(basepath))
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()

class MathWorkOutPut(BaseModel):
    is_math_problem: bool = Field(description="Whether the input is a math problem")
    reasoning: str = Field(description="The result of the math operation")

guarddrail_agent = Agent(
    name = "Guardrail Agent",
    instructions = "check if the user asking you to do their math work.",
    model=model,
    output_type=MathWorkOutPut,
)

@input_guardrail
async def  math_guarddrail(ctx:RunContextWrapper[None], agent:Agent, input:str | list[TResponseInputItem]) -> GuardrailFunctionOutput:
    print("****************************** I am inside (input_guardrail.math_guarddrail) *******************************")
    print(f"Guardrail checking input: {input}")
    print(f"*********** The RunContextWrapper context: {ctx}\n and context.context: {ctx.context}\n ")
    result = await Runner.run(guarddrail_agent, input,context= ctx.context)
    print(f"***********Guardrail agent output: **************{result}")
    return GuardrailFunctionOutput(
        output_info=result.final_output.dict() if result.final_output else None,
        tripwire_triggered=result.final_output.is_math_problem if result.final_output else False,
    )

agent = Agent(
    name="Example Agent with Guardrail",
    instructions="you are customer support agent, You help customer with their question.",
    model=model,
    input_guardrails=[math_guarddrail],
)


async def main():
    # This should trip the guardrail
    try:
        await Runner.run(agent, "Hello, can you help me solve for x: 2x + 3 = 11?")
        print("Guardrail didn't trip - this is unexpected")

    except InputGuardrailTripwireTriggered:
        print("Math homework guardrail tripped")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())