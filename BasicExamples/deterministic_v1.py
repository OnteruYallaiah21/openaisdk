# **************** START CONFIGURATION ****************************
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))
load_dotenv()
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()
print("✅ Model loaded from config")
# ************** END OF CONFIGURATION ******************************

import asyncio
from pydantic import BaseModel
from agents import Agent, Runner, RunContextWrapper, AgentHooks,AgentHookContext
from pydantic import BaseModel
from typing import Any, Annotated, Optional, Dict, List, Union,Callable

# 2. DATA STRUCTURES: Define the "Contract" between agents
class RefundEligibility(BaseModel):
    is_eligible: bool
    reasoning: str
    risk_level: str

class TriagePromptInstruction(BaseModel):
    triage_instruction: str
    policy_checker_agent_instruction: str
    refund_processor_agent_instruction: str
    

# 3. AGENTS: Define specialized roles
triage_agent = Agent(
    name="triage_agent",
    model=model,
    instructions="Extract the product name, purchase date, and core complaint from the user's message."
)

policy_checker_agent = Agent(
    name="policy_checker_agent",
    model=model,
    instructions="""Judge eligibility based on:
    1. Refund must be within 30 days of purchase.
    2. 'Changed my mind' is NOT a valid reason.
    Output the eligibility, a brief reason, and risk level.""",
    output_type=RefundEligibility,
)

refund_processor_agent = Agent(
    name="refund_processor_agent",
    model=model,
    instructions="Draft a professional refund approval email with bank processing details.",
    output_type=str,
)

# 4. EXECUTION: The Linear Pipeline
async def main():
    customer_input = "I bought the SuperWidget 10 days ago, but it arrived broken and I want my money back."

    print(f"--- Processing Request ---\nInput: {customer_input}\n")

    # STEP 1: Extraction
    triage_result = await Runner.run(triage_agent, customer_input)
    print(f"✔ Triage Data: {triage_result.final_output}")

    # STEP 2: Logic Check (The Gate)
    check_result = await Runner.run(
        policy_checker_agent, 
        triage_result.final_output
    )
    
    decision = check_result.final_output
    
    if not decision.is_eligible:
        print(f"❌ REJECTED: {decision.reasoning}")
        return

    print(f"✅ APPROVED: (Risk: {decision.risk_level})")

    # STEP 3: Final Output
    final_email = await Runner.run(
        refund_processor_agent, 
        f"Data: {triage_result.final_output}\nReason: {decision.reasoning}"
    )
    
    print("\n--- Final Customer Email ---")
    print(final_email.final_output)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Internal Error: {e}")