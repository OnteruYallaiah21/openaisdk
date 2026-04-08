#==============================DEVELOPER INFO======================================
#Name : Onteru Yallaiah 
#email : yonteru.dev.ai@gmail.com
#date : 2025-06-17
#Description : Fixed JSON validation error by enforcing clean extraction.

# **************** START CONFIGURATION & CUSTOM IMPORTS  ****************************
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
# ************** END OF CONFIGURATION & CUSTOM IMPORTS  ******************************

import asyncio
from agents import Agent, Runner
from pydantic import BaseModel
from typing import Literal

# 1. THE REGISTRY: Instructions refined to prevent JSON failures
REGISTRY = {
    "triage": {
        "name": "Claim_Triage_Agent",
        "instructions": "Extract the item name, its estimated value, and the description of damage. Provide a concise summary without markdown formatting."
    },
    "auditor": {
        "name": "Policy_Auditor_Agent",
        "instructions": "Analyze the claim summary. Determine eligibility based on: 1. Value < $5000. 2. Damage is accidental. You MUST return a valid JSON object matching the schema."
    },
    "processor": {
        "name": "Settlement_Agent",
        "instructions": "Draft a formal approval letter for the insurance claim."
    }
}

# 2. DATA MODELS
class ClaimAudit(BaseModel):
    is_eligible: bool
    risk_level: Literal["Low", "Medium", "High"]
    reasoning: str

# 3. AGENT INITIALIZATION
triage_agent = Agent(
    name=REGISTRY["triage"]["name"],
    instructions=REGISTRY["triage"]["instructions"],
    model=model,
)

policy_audit_agent = Agent(
    name=REGISTRY["auditor"]["name"],
    instructions=REGISTRY["auditor"]["instructions"],
    output_type=ClaimAudit, # This tells the agent to use tool-calling/JSON mode
    model=model,
)

settlement_agent = Agent(
    name=REGISTRY["processor"]["name"],
    instructions=REGISTRY["processor"]["instructions"],
    model=model
)

# 4. EXECUTION FLOW
async def main():
    customer_input = "My professional camera (Value: $2500) fell into a lake during a shoot. It's a total loss."
    
    print(f"--- Processing New Claim ---\nInput: {customer_input}\n")

    # STEP 1: Run Triage (Fact Extraction)
    triage_result = await Runner.run(triage_agent, customer_input)
    clean_context = triage_result.final_output
    print(f"✔ Triage Complete. Data: {clean_context}")

    # STEP 2: Run the Logic Gate (Audit)
    # We pass the clean context from Triage into the Auditor
    try:
        audit_result = await Runner.run(
            policy_audit_agent, 
            clean_context
        )
        decision = audit_result.final_output
    except Exception as e:
        print(f"⚠️ Audit Agent failed to validate JSON. Error: {e}")
        return

    # DETERMINISTIC BUSINESS RULES
    if not decision.is_eligible:
        print(f"❌ CLAIM REJECTED: {decision.reasoning}")
        return

    print(f"✅ CLAIM APPROVED: (Risk: {decision.risk_level})")

    # STEP 3: Final Settlement
    final_letter = await Runner.run(
        settlement_agent, 
        f"Generate letter for: {clean_context}. Reasoning: {decision.reasoning}"
    )
    
    print("\n--- Final Settlement Document ---")
    print(final_letter.final_output)

if __name__ == "__main__":
    asyncio.run(main())