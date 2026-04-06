import os
from pathlib import Path
from random import random
import sys
rootpath = Path(__file__).resolve().parent.parent
sys.path.append(str(rootpath))
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()
from agents import Agent, AgentHookContext, Runner, AgentHooks, RunHooks, function_tool, RunContextWrapper
from typing import (Any, Annotated, Dict, List, Literal, Optional, Union, Literal)
from pydantic import BaseModel

class cunstom_prompt(BaseModel):
    role: Literal["manager", "Developer", "HR Department", "Salesteam"]


def cunstom_Instructions(run_context:RunContextWrapper, agent:Agent) ->str :
    context = run_context.context
    print("[Yallesh Debug in Custom instructions]. context :{context}, agent: {agent.name}")
    if context.role == "manager": 
         return "you are a manger who can manage all business operations when some one ask anything you need to redirect specifc deparatment based on his intent "
    elif context.role == "Developer":
        return "you are soft ware devloper you need to answer the all the question and imporant phases of sdlc what type of technolgy is more stable and more suitable for you application you need to guide the people "
    elif context.role == "HR Department":
        return "you are helpful hr department  you need to assistan all the hr questions like when he gets paid  what is the bouns and you need to manage the human resouces in the organization"
    elif context.role == "Salesteam":
        return "you are a helpful salesteam assistant based on if you get any leads you need to bragin  the customer up to his  some kind 50% threshold level you need to close the deals"
    else:
        return "you are a helpful assistant for the organization you need to assist the people in the organization based on their intent you need to redirect them to the specific department"
    
#=========================================tools defination start here ================================
@function_tool
def analyze_requirements(req: str) -> str:
    return f"[Developer Tool] Analyzed requirements: {req}. Suggested microservices architecture."

@function_tool
def suggest_tech_stack(app_type: str) -> str:
    return f"[Developer Tool] Recommended stack for {app_type}: React + FastAPI + PostgreSQL + Docker."

@function_tool
def explain_sdlc(phase: str) -> str:
    return f"[Developer Tool] SDLC Phase '{phase}': Includes planning, design, development, testing, deployment."
@function_tool
def get_salary_details(employee_id: str) -> str:
    return f"[HR Tool] Salary details for {employee_id}: Paid monthly, includes bonus eligibility."

@function_tool
def check_leave_balance(employee_id: str) -> str:
    return f"[HR Tool] Leave balance for {employee_id}: 12 casual leaves, 8 sick leaves remaining."

@function_tool
def get_company_policies(policy_type: str) -> str:
    return f"[HR Tool] Policy '{policy_type}': Standard company HR policies applied."
@function_tool
def generate_lead(customer_name: str) -> str:
    return f"[Sales Tool] Lead generated for {customer_name}. Added to CRM pipeline."

@function_tool
def pitch_product(product: str) -> str:
    return f"[Sales Tool] Pitch: {product} increases ROI by 40% and reduces cost by 25%."

@function_tool
def close_deal(customer_name: str) -> str:
    return f"[Sales Tool] Deal closed with {customer_name}. Revenue recorded successfully."
@function_tool
def route_to_department(intent: str) -> str:
    return f"[Manager Tool] Based on intent '{intent}', routing to appropriate department."

@function_tool
def get_business_status() -> str:
    return "[Manager Tool] Business Status: All departments operating efficiently. Revenue up by 12%."

@function_tool
def escalate_issue(issue: str) -> str:
    return f"[Manager Tool] Issue '{issue}' escalated to leadership team."
#=========================================tools defination end here =================================
#============================================================ Agent configuration start here 
devloper_agnet = Agent(
    name="devloper_agnet",
    instructions=cunstom_Instructions,
    model=model,
    tools=[analyze_requirements, suggest_tech_stack, explain_sdlc]
)

hr_agnet = Agent(
    name="hr_agnet",
    instructions=cunstom_Instructions,
    model=model,
    tools=[get_salary_details, check_leave_balance, get_company_policies]
)

salesteam_agent = Agent(
    name="salesteam_agent",
    instructions=cunstom_Instructions,
    model=model,
    tools=[generate_lead, pitch_product, close_deal]
)

manager_agent = Agent(
    name="manager_agent",
    instructions=cunstom_Instructions,
    model=model,
    handoffs=[devloper_agnet, hr_agnet, salesteam_agent],
    tools=[route_to_department, get_business_status, escalate_issue]

)
#============================================================= Agent Configration end here 

async def main():

    context = cunstom_prompt(role="manager")
    result = await Runner.run(manager_agent, "What is the current status of our business and route me to the appropriate department for a new customer lead?", context=context)
    print("Final Result:", result.final_output)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())