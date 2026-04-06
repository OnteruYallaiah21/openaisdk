from agents import Agent, function_tool
from pydantic import BaseModel
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
import asyncio
from agents import (
    Agent, Runner, input_guardrail, 
    GuardrailFunctionOutput, InputGuardrailTripwireTriggered,
    enable_verbose_stdout_logging
)

# STEP 1: Enable the debug logs to see the flow
enable_verbose_stdout_logging()

# STEP 2: Define the Guardrail Function
@input_guardrail(run_in_parallel=False) # Blocking mode for clear logs
async def math_check(ctx, agent, input_text):
    print(f"DEBUG: [Guardrail] Checking input: {input_text}")
    
    # Logic: Trip if 'x' or '+' or '=' is in the text
    is_math = any(char in input_text for char in ["+", "=", "x"])
    
    return GuardrailFunctionOutput(
        tripwire_triggered=is_math,
        output_info={"detected_math": is_math}
    )

# STEP 3: Define the Main Agent
support_agent = Agent(
    name="Support Agent",
    instructions="You are a helpful customer support assistant.",
    input_guardrails=[math_check]
)

async def main():
    print("--- STARTING RUN ---")
    try:
        # This will trigger the math_check guardrail
        await Runner.run(support_agent, "Solve for x: 2+2")
    except InputGuardrailTripwireTriggered:
        print("--- RESULT: Execution blocked by Guardrail ---")

if __name__ == "__main__":
    asyncio.run(main())