#==============================DEVELOPER INFO======================================
#Name : Onteru Yallaiah 
#email : yonteru.dev.ai@gmail.com
#date : 2025-06-17
#Description : Enhanced JSONCleaner to handle hidden characters/non-breaking spaces and improved regex.

# **************** START CONFIGURATION & CUSTOM IMPORTS  ****************************
import os
import sys
import inspect
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from typing import Any, Dict, List, Optional, Union, Literal
from pydantic import BaseModel
import time
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))
load_dotenv()
from utils.cleaner_functions import JSONCleaner
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()
print("✅ Model loaded from config")
import logging

logger = logging.getLogger(__name__)
# ************** END OF CONFIGURATION & CUSTOM IMPORTS  ******************************

import asyncio
from agents import Agent, Runner,RunContextWrapper, AgentHooks,AgentHookContext,FunctionTool, input_guardrail, GuardrailFunctionOutput




# --- DEBUGGING UTILITY ---
def log_info(message: str):
    """Prints the line number in bold yellow, but the message in default color."""
    frame = inspect.currentframe().f_back
    line_no = frame.f_lineno
    yellow = "\033[93m"
    bold = "\033[1m"
    reset = "\033[0m"
    print(f"{bold}{yellow}[LINE {line_no}]{reset} INFO: {message}")

# 1. THE REGISTRY
REGISTRY = {
    "triage": {
        "name": "Claim_Triage_Agent",
        "instructions": "Extract the item name, its estimated value, and the description of damage. Provide a concise summary."
    },
    "auditor": {
        "name": "Policy_Auditor_Agent",
        "instructions": (
            "You are a Senior Claims Auditor. Analyze the claim summary against these rules:\n"
            "1. Value must be under $500.\n"
            "2. Damage must be accidental.\n\n"
            "Output JSON with keys: 'is_eligible' (bool), 'risk_level' (Low/Medium/High), and 'reasoning' (string)."
        )
    },
    "processor": {
        "name": "Settlement_Agent",
        "instructions": "Draft a formal approval letter for the insurance claim based on the provided details."
    },
    "guraddril_agnet":{
        "name":"input_guarddrail_agent",
        "instructions":("you are E-commerce assistant now you responsevility is if the user ask the question check that question is strcily realted our queries\n"
                        "1.if the question unrealted to the our business block him with true or false in pydantic model\n"
                        "")
        

    }
}
#################################################### 1. TOOLS Intilization ##################################
  #============================================ start sync tools =============
@input_guardrail(name="user_inpout_check", run_in_parallel=False)
def user_inpout_check(context, agent, user_input):
    log_info(f"The control is in the -------user_inpout_check---------------")
    log_info(f"printing the Context----user_inpout_check, context:{context}")
    log_info(f"printing the Context----user_inpout_check, Agent:{agent}")
    forbidden_words = ["sex", "marrige", "looking for a girl--------user_inpout_check-------------"]
    
    is_off_topic = any(word in user_input.lower() for word in forbidden_words)

    return GuardrailFunctionOutput(
        output_info={"detected_words": forbidden_words} if is_off_topic else None,
        tripwire_triggered=is_off_topic
    )

  #=========================================== end of sync tools =============
  #============================================ start async tools =============
@input_guardrail
async def llm_user_input_guraddrail(context, agent, user_input):
    log_info("Running LLM Guardrail (Lite Version)...")
    log_info(f"printing the Context----llm_user_input_guraddrail before llm call, context:{context}")
    log_info(f"printing the Context----llm_user_input_guraddrail before llm call, Agent:{agent}")
    # 1. Get raw output from the guardrail agent
    result = await Runner.run(guarddrail_agent, user_input)

    log_info(f"printing the Context----llm_user_input_guraddrail after llm call, context:{context}")
    log_info(f"printing the Context----llm_user_input_guraddrail after llm call, Agent:{agent}")
    # 2. Clean to a dictionary
    cleaned_data = JSONCleaner.process(result.final_output)
    
    # 3. Simple Extraction with a default fallback
    # We look for the key, but if it's missing, we assume False (don't block)
    is_off_topic = cleaned_data.get("out_of_topic", False)

    # 4. Return the required dataclass
    return GuardrailFunctionOutput(
        tripwire_triggered=is_off_topic,
        output_info={"reason": "LLM flagged as off-topic"} if is_off_topic else None
    )

  #=========================================== end of async tools =============

###################################################  2. DATA MODELS #########################################

class ClaimAudit(BaseModel):
    is_eligible: bool
    risk_level: Literal["Low", "Medium", "High"]
    reasoning: str

class InputGuardrail(BaseModel):
      out_of_topic: bool

####################################################  3. AGENT INITIALIZATION ################################
guarddrail_agent=Agent(
    name=REGISTRY["guraddril_agnet"]["name"],
    instructions=REGISTRY["guraddril_agnet"]["instructions"],
    model=model,
)
triage_agent = Agent(
    name=REGISTRY["triage"]["name"],
    instructions=REGISTRY["triage"]["instructions"],
    model=model,
    input_guardrails=[user_inpout_check,llm_user_input_guraddrail]
)

policy_audit_agent = Agent(
    name=REGISTRY["auditor"]["name"],
    instructions=REGISTRY["auditor"]["instructions"],
    model=model,
)

settlement_agent = Agent(
    name=REGISTRY["processor"]["name"],
    instructions=REGISTRY["processor"]["instructions"],
    model=model
)

# 4. EXECUTION FLOW
async def main():
    user_question = input("Hey I am your personal assistant do you have any questions related to to product defecets and user quesries: ")
    

    
    log_info(f"--- Processing New Claim ---\nInput: {user_question}\n")
    log_info(f"--- Printing RunContextWrapper before sending to llm _____{RunContextWrapper}")
    # STEP 1: Run Triage
    triage_result = await Runner.run(triage_agent, user_question)

    log_info(f"The final result opr return typoe oafter on sucessful llm call{triage_result}")
    import pprint
    pprint.pprint(triage_result.__dict__)

    log_info(f"--- Printing RunContextWrapper after [triage_agent] _____{RunContextWrapper}")
    clean_context = triage_result.final_output
    log_info(f"✔ Triage Complete. Data: {clean_context}")

    # STEP 2: Run the Logic Gate (Audit)
    audit_raw_response = await Runner.run(
        policy_audit_agent, 
        f"Please audit this claim based on these details: {clean_context}"
    )
    
    # Use JSONCleaner to safely parse the output
    cleaned_data = JSONCleaner.process(audit_raw_response.final_output)
    
    try:
        # Validate against the Pydantic model manually
        decision = ClaimAudit(**cleaned_data)
    except Exception as e:
        log_info(f"⚠️ Failed to construct ClaimAudit model. Error: {e}")
        log_info(f"🔍 Raw JSON attempt: {audit_raw_response.final_output}")
        return

    # DETERMINISTIC BUSINESS RULES
    if not decision.is_eligible:
        log_info(f"❌ CLAIM REJECTED: {decision.reasoning}")
        return

    log_info(f"✅ CLAIM APPROVED: (Risk: {decision.risk_level})")

    # STEP 3: Final Settlement
    final_letter = await Runner.run(
        settlement_agent, 
        f"Generate letter for: {clean_context}. Reasoning: {decision.reasoning}"
    )
    
    log_info("--- Final Settlement Document Generated ---")
    print(final_letter.final_output)

if __name__ == "__main__":
    asyncio.run(main())




"""
============================================== OpenAI SDK Observations =================================================

"""