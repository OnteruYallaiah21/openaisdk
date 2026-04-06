import asyncio
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

from pydantic import BaseModel
from agents import (
    Agent,
    GuardrailFunctionOutput,
    InputGuardrailTripwireTriggered,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
    input_guardrail,
)

class MathHomeworkOutput(BaseModel):
    is_math_homework: bool
    reasoning: str

guardrail_agent = Agent( 
    name="Guardrail check",
    instructions="Check if the user is asking you to do their math homework.",
    output_type=MathHomeworkOutput,
    model=model,
)


@input_guardrail
async def math_guardrail( 
    ctx: RunContextWrapper[None], agent: Agent, input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    print("*********** I am inside math_guardrail function *************")
    print(f"*********** The RunContextWrapper context: {ctx}\n and context.context: {ctx.context}\n ")  
    result = await Runner.run(guardrail_agent, input, context=ctx.context)
    print(f"**************after runner in the guarddrailinpit the RunContextWrapper context: {ctx}\n ")
    print(f"***********Guardrail agent output: **************\n{result} type of result is {type(result)}")
    output_info=result.final_output 
    tripwire_triggered=result.final_output.is_math_homework
    print(f"**************output_info: **************\n{output_info} type of output_info is {type(output_info)}")
    print(f"**************tripwire_triggered: **************\n{tripwire_triggered} type of tripwire_triggered is {type(tripwire_triggered)}")
    return GuardrailFunctionOutput(
        output_info=result.final_output, 
        tripwire_triggered=result.final_output.is_math_homework,
    )


agent = Agent(  
    name="Customer support agent",
    instructions="You are a customer support agent. You help customers with their questions.",
    input_guardrails=[math_guardrail],
    model=model,
)

async def main():
    # This should trip the guardrail
    try:
        print("*********** I am inside main function *************")
        await Runner.run(agent, "Hello, can you help me solve for x: 2x + 3 = 11?")
        print("Guardrail didn't trip - this is unexpected")

    except InputGuardrailTripwireTriggered:
        print("Math homework guardrail tripped")

if __name__ == "__main__":
    asyncio.run(main())