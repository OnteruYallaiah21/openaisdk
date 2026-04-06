import asyncio
from pathlib import Path
import sys
from typing import Optional
import re

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from agents import Agent, Runner, function_tool, AgentHooks, AgentHookContext, RunContextWrapper
from llm_model_config.llm_model_config import ModelSingleton
from searchuser import search_user
from email_sender import EmailSender

# ====================== MODEL ======================
model = ModelSingleton.get_instance()

# ====================== DEBUG HOOKS ======================
class DebugAgentHooks(AgentHooks):
    def __init__(self, display_name: str):
        self.display_name = display_name
        self.counter = 0

    async def on_start(self, context: AgentHookContext, agent: Agent) -> None:
        self.counter += 1
        print(f"[{self.display_name}] {self.counter}: Agent {agent.name} START → {context.turn_input}")

    async def on_end(self, context: RunContextWrapper, agent: Agent, output: str) -> None:
        self.counter += 1
        print(f"[{self.display_name}] {self.counter}: Agent {agent.name} END → {output}")

# ====================== TOOLS ======================
@function_tool
def code_review(task: str) -> str:
    return f"Dev team reviewed task: '{task}'."

@function_tool
def hr_evaluation(candidate_name: str) -> str:
    return f"HR evaluated candidate '{candidate_name}' successfully."

@function_tool
def sales_pitch(product: str) -> str:
    return f"Sales pitch prepared for product '{product}'."

@function_tool
def manager_approval(document: str) -> str:
    return f"Manager approved document '{document}'."

# ====================== EMAIL TOOL ======================
def send_emails(sender_name: str,
                recipient_name: str,
                recipient_email: str,
                body: str) -> str:
    """
    Send an email using sender configuration loaded from search_user.
    """
    try:
        senderdetails = search_user(sender_name)
        if not senderdetails:
            raise ValueError(f"Sender '{sender_name}' not found in user database.")
        sender_email = senderdetails["smtp_username"]
        sender_pass = senderdetails["smtp_password"]

        sender = EmailSender(sender_email=sender_email,
                             app_password=sender_pass,
                             resume_file=None)
        success = sender.send_email(
            recruiter_email=recipient_email,
            recruiter_name=recipient_name,
            subject="Automated Message",
            body=body,
            attach_resume=False
        )
        return f"✅ Email sent to {recipient_email}" if success else f"❌ Failed to send"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ====================== EMAIL AGENT ======================
email_agent = Agent(
    name="EmailCommunicationAgent",
    instructions="Send emails based on user request. Extract recipient and body.",
    tools=[send_emails],
    model=model,
    hooks=DebugAgentHooks("Email Agent")
)

# ====================== COMPANY AGENTS ======================
dev_agent = Agent(name="Dev Agent", instructions="Dev questions only.", tools=[code_review], model=model, hooks=DebugAgentHooks("Dev Agent"))
hr_agent = Agent(name="HR Agent", instructions="HR questions only.", tools=[hr_evaluation], model=model, hooks=DebugAgentHooks("HR Agent"))
sales_agent = Agent(name="Sales Agent", instructions="Sales questions only.", tools=[sales_pitch], model=model, hooks=DebugAgentHooks("Sales Agent"))
manager_agent = Agent(name="Manager Agent", instructions="Manager questions only.", tools=[manager_approval], model=model, hooks=DebugAgentHooks("Manager Agent"))

agent_map = {
    "dev": dev_agent,
    "hr": hr_agent,
    "sales": sales_agent,
    "manager": manager_agent,
    "email": email_agent
}

# ====================== GUARDRAIL ======================
input_guardrail_agent = Agent(
    name="InputGuardrailAgent",
    instructions="""
    You are a guardrail agent. Only respond with "allow" if the input is company-related
    (HR, Dev, Sales, Manager, Email tasks). Respond with "block" for personal, unsafe,
    or unrelated inputs. Do NOT generate any extra text
    if some want to route to email agnet and  do not block.
    """,
    model=model,
    hooks=DebugAgentHooks("Guardrail"),
)

async def input_run_guardrail(user_question: str) -> bool:
    result = await Runner.run(input_guardrail_agent, input=user_question)
    output = result.final_output.strip().lower()
    return output == "allow"

# ====================== LLM ROUTING ======================
def llm_router(user_question: str) -> str:
    """
    Simple LLM routing based on keywords.
    """
    question_lower = user_question.lower()
    if "email" in question_lower or "send email" in question_lower:
        return "email"
    if "dev" in question_lower or "code" in question_lower or "task" in question_lower:
        return "dev"
    if "hr" in question_lower or "candidate" in question_lower:
        return "hr"
    if "sales" in question_lower or "pitch" in question_lower:
        return "sales"
    if "manager" in question_lower or "approve" in question_lower or "document" in question_lower:
        return "manager"
    return "hr"  # default fallback

async def dynamic_routing_llm(user_question: str) -> Optional[Agent]:
    allowed = await input_run_guardrail(user_question)
    if not allowed:
        return None
    agent_key = llm_router(user_question)
    return agent_map.get(agent_key)

# ====================== ORCHESTRATOR ======================
async def company_orchestrator(user_question: str) -> str:
    print(f"\nUser Input: {user_question}\n")
    agent = await dynamic_routing_llm(user_question)
    if not agent:
        return "🚨 Input rejected by guardrail."
    result = await Runner.run(agent, input=user_question)
    return result.final_output

# ====================== MAIN LOOP ======================
async def main():
    print("==== Company Simulator with LLM Routing & Email Agent ====")
    while True:
        user_input = input("\nEnter your question (or 'exit' to quit): ").strip()
        if user_input.lower() == "exit":
            break
        output = await company_orchestrator(user_input)
        print(f"\nFinal Output:\n{output}\n")

if __name__ == "__main__":
    asyncio.run(main())