import asyncio
import os
import sys
import smtplib
from pathlib import Path
from email.message import EmailMessage
from typing import Optional, List, Dict, Union, Any
from pydantic import BaseModel

# ------------------- SYSTEM SETUP -------------------
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

from agents import (
    Agent,
    AgentHooks,
    Runner,
    function_tool,
    RunContextWrapper,
    AgentHookContext,
    ToolInputGuardrailData,
    ToolGuardrailFunctionOutput,
    ToolOutputGuardrailData,
    ToolOutputGuardrailTripwireTriggered,
    tool_input_guardrail,
    tool_output_guardrail,
)

# Import your existing search_user service
from searchuser import search_user

try:
    from llm_model_config.llm_model_config import ModelSingleton
    model = ModelSingleton.get_instance()
    print("✅ Model loaded from config")
except ImportError:
    from agents.models import OpenAIModel
    model = OpenAIModel(model_id="gpt-4o")
    print("✅ Using fallback OpenAI model")


# ------------------- DEBUG HOOKS -------------------
class DebugAgentHooks(AgentHooks):
    def __init__(self, display_name: str):
        self.display_name = display_name
        self.counter = 0

    async def on_start(self, context: AgentHookContext, agent: Agent) -> None:
        self.counter += 1
        print(f"\n{'🟢 AGENT START'.center(60,'-')}")
        print(f"[{self.display_name}] Turn #{self.counter}")
        print(f"[{self.display_name}] Agent: {agent.name}")
        print(f"[{self.display_name}] Input: {context.turn_input}")
        print(f"{'-'*60}")

    async def on_end(self, context: RunContextWrapper, agent: Agent, output: str) -> None:
        self.counter += 1
        print(f"\n{'🔴 AGENT END'.center(60,'-')}")
        print(f"[{self.display_name}] Turn #{self.counter}")
        print(f"[{self.display_name}] Agent: {agent.name}")
        print(f"[{self.display_name}] Output: {output[:300]}..." if len(output) > 300 else f"[{self.display_name}] Output: {output}")
        print(f"{'-'*60}")


# ------------------- EMAIL SENDER -------------------
class EmailSender:
    """Send emails using Gmail SMTP"""
    def __init__(self, sender_email: str, app_password: str):
        self.sender_email = sender_email
        self.app_password = app_password
        print(f"    📧 [Control] EmailSender: {sender_email[:10]}...")

    def send_email(self, recipient_email: str, subject: str, body: str) -> bool:
        print(f"    >>> [SMTP] Sending to {recipient_email}")
        try:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            msg.set_content(body)

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(self.sender_email, self.app_password)
                smtp.send_message(msg)
            print(f"    ✅ [SMTP] Email sent successfully")
            return True
        except Exception as e:
            print(f"    ❌ [SMTP Error] {e}")
            return False


# ------------------- TOOLS -------------------
@function_tool
def send_emails(sender_name: str, recipient_name: str, recipient_email: str, body: str) -> str:
    """Send email using credentials from search_user service"""
    print(f"\n>>> [Tool: send_emails] Called")
    print(f"    → Sender: {sender_name}")
    print(f"    → Recipient: {recipient_email}")
    
    # Use your existing search_user service
    results = search_user(sender_name)
    
    if not results:
        return f"❌ Error: No credentials found for '{sender_name}'"

    user_data = results[0]
    print(f"    → Found user: {user_data.get('smtp_username', 'No email')}")
    
    sender = EmailSender(
        sender_email=user_data.get("smtp_username"),
        app_password=user_data.get("smtp_password")
    )

    # Format body with recipient name if placeholder exists
    formatted_body = body.format(name=recipient_name) if "{name}" in body else body

    success = sender.send_email(
        recipient_email=recipient_email,
        subject="Company Notification",
        body=formatted_body
    )

    return f"✅ Email sent successfully from {sender_name} to {recipient_email}" if success else "❌ SMTP Failure. Please check App Password."


@function_tool
def code_review(task: str) -> str:
    """Review code or development task"""
    print(f"\n>>> [Tool: code_review] Task: {task[:60]}...")
    return f"✅ Dev team reviewed: '{task}'\n📊 Status: Code quality approved. Ready for deployment."


@function_tool
def hr_evaluation(candidate_name: str, position: str = "") -> str:
    """Evaluate HR candidate or handle HR request"""
    print(f"\n>>> [Tool: hr_evaluation] Candidate: {candidate_name}")
    if position:
        return f"✅ HR Evaluation for {candidate_name} ({position}):\n   • Skills: Matched\n   • Experience: Verified\n   • Status: Recommended for interview"
    return f"✅ HR evaluation completed for '{candidate_name}'. Candidate meets requirements."


@function_tool
def sales_pitch(product: str, target_audience: str = "") -> str:
    """Create sales pitch for product"""
    print(f"\n>>> [Tool: sales_pitch] Product: {product}")
    pitch = f"🚀 SALES PITCH for '{product}':\n"
    pitch += f"   • Value Proposition: Innovative solution for market needs\n"
    pitch += f"   • Key Features: Scalable, Reliable, Cost-effective\n"
    if target_audience:
        pitch += f"   • Target Audience: {target_audience}\n"
    pitch += f"   • Projected ROI: 30% increase in Q3"
    return pitch


@function_tool
def manager_approval(document: str, department: str = "") -> str:
    """Approve document or request"""
    print(f"\n>>> [Tool: manager_approval] Document: {document}")
    approval = f"✅ MANAGER APPROVAL for '{document}':\n"
    approval += f"   • Status: Approved\n"
    approval += f"   • Effective Date: Immediate\n"
    if department:
        approval += f"   • Department: {department}\n"
    approval += f"   • Signed: Management Team"
    return approval


@function_tool
def ceo_decision(strategy: str, impact: str = "") -> str:
    """Make strategic CEO decision"""
    print(f"\n>>> [Tool: ceo_decision] Strategy: {strategy}")
    decision = f"👔 CEO STRATEGIC DECISION:\n"
    decision += f"   • Initiative: '{strategy}'\n"
    decision += f"   • Board Approval: Granted\n"
    if impact:
        decision += f"   • Projected Impact: {impact}\n"
    decision += f"   • Implementation: Effective immediately\n"
    decision += f"   • Next Steps: Department heads to execute"
    return decision


# ------------------- GUARDRAILS -------------------
@tool_input_guardrail
async def reject_inappropriate_input(
    data: ToolInputGuardrailData,
    agent: Agent,
) -> ToolGuardrailFunctionOutput:
    """Block inappropriate tool inputs"""
    print(f"\n🛡️ [Input Guardrail] Checking tool input")
    
    inappropriate_keywords = ["hack", "exploit", "illegal", "threat", "abuse", "password", "secret"]
    input_str = str(data.context).lower()
    
    for keyword in inappropriate_keywords:
        if keyword in input_str:
            print(f"❌ [Guardrail] Blocked: contains '{keyword}'")
            return ToolGuardrailFunctionOutput(
                output_info=f"Blocked inappropriate input containing '{keyword}'",
                tripwire_triggered=True,
            )
    
    print(f"✅ [Guardrail] Input approved")
    return ToolGuardrailFunctionOutput(
        output_info="Input allowed",
        tripwire_triggered=False,
    )


@tool_output_guardrail
async def block_inappropriate_output(
    data: ToolOutputGuardrailData,
    agent: Agent,
) -> None:
    """Block inappropriate tool outputs"""
    print(f"\n🛡️ [Output Guardrail] Checking tool output")
    
    # Don't block normal business outputs
    output_str = str(data.output).lower()
    
    # Only block truly sensitive information
    sensitive_keywords = ["database password", "api key", "secret token"]
    
    for keyword in sensitive_keywords:
        if keyword in output_str:
            print(f"❌ [Guardrail] Blocking output containing '{keyword}'")
            raise ToolOutputGuardrailTripwireTriggered(
                f"Output blocked: contains sensitive keyword '{keyword}'"
            )
    
    print(f"✅ [Guardrail] Output approved")


# ------------------- CREATE AGENTS -------------------
agents = []

# Email Agent
email_agent = Agent(
    name="Email Agent",
    instructions="""Handle user requests to send emails.
    
    Steps:
    1. Extract sender's name from the user input (e.g., "my name is X")
    2. Extract recipient's email address
    3. Extract the message content
    4. Call send_emails tool with all extracted information
    
    If any information is missing, ask the user politely for it.""",
    tools=[send_emails],
    model=model,
    hooks=DebugAgentHooks("📧 EMAIL"),
)
agents.append(email_agent)

# Dev Agent
dev_agent = Agent(
    name="Dev Agent",
    instructions="""Handle development-related tasks:
    - Code reviews and quality checks
    - Bug fixes and technical problems
    - Project development questions
    - Technical architecture decisions
    
    Use the code_review tool for code-related tasks.
    Be technical and precise in your responses.""",
    tools=[code_review],
    model=model,
    hooks=DebugAgentHooks("💻 DEV"),
)
agents.append(dev_agent)

# HR Agent
hr_agent = Agent(
    name="HR Agent",
    instructions="""Handle HR-related tasks:
    - Candidate evaluation and recruitment
    - Leave requests and attendance
    - Salary and compensation issues
    - Employee benefits and concerns
    - Company policies and procedures
    
    Use hr_evaluation tool for candidate assessments.
    Be empathetic and professional in HR matters.""",
    tools=[hr_evaluation],
    model=model,
    hooks=DebugAgentHooks("👥 HR"),
)
agents.append(hr_agent)

# Sales Agent
sales_agent = Agent(
    name="Sales Agent",
    instructions="""Handle sales-related tasks:
    - Creating compelling sales pitches
    - Product marketing strategies
    - Customer acquisition plans
    - Revenue growth initiatives
    
    Use sales_pitch tool to create professional pitches.
    Be persuasive and results-oriented.""",
    tools=[sales_pitch],
    model=model,
    hooks=DebugAgentHooks("📈 SALES"),
)
agents.append(sales_agent)

# Manager Agent
manager_agent = Agent(
    name="Manager Agent",
    instructions="""Handle management-related tasks:
    - Document approvals and reviews
    - Team management and coordination
    - Resource allocation decisions
    - Project oversight and reporting
    
    Use manager_approval tool for document approvals.
    Be decisive and clear in communications.""",
    tools=[manager_approval],
    model=model,
    hooks=DebugAgentHooks("👔 MANAGER"),
)
agents.append(manager_agent)

# CEO Agent
ceo_agent = Agent(
    name="CEO Agent",
    instructions="""Handle strategic decisions:
    - Corporate strategy and direction
    - Major investments and initiatives
    - Organizational changes
    - High-level partnerships
    
    Use ceo_decision tool for strategic approvals.
    Think big picture and long-term impact.""",
    tools=[ceo_decision],
    model=model,
    hooks=DebugAgentHooks("👑 CEO"),
)
agents.append(ceo_agent)

# Guardrail Agent
guardrail_agent = Agent(
    name="Guardrail Agent",
    instructions="""You are a security guardrail.
    Respond ONLY with 'allow' for ANY business-related questions including:
    - Emails, notifications, communications
    - HR, leave, salary, benefits
    - Development, code, bugs, technical issues
    - Sales, marketing, pitches
    - Management, approvals, documents
    - Strategy, CEO decisions
    
    Respond with 'block' ONLY for:
    - Profanity or harassment
    - Illegal activities
    - Non-business personal questions
    
    Just say 'allow' or 'block' - nothing else.""",
    model=model,
    hooks=DebugAgentHooks("🛡️ GUARDRAIL"),
)


# ------------------- ROUTING -------------------
class RoutingRequest(BaseModel):
    user_question: str
    suggested_agent: Optional[str] = None


async def dynamic_routing(user_question: str) -> Optional[Agent]:
    """Route user question to appropriate agent"""
    print(f"\n{'🔀 ROUTING'.center(60,'=')}")
    print(f"Question: {user_question}")
    
    # First check guardrail
    gr_result = await Runner.run(guardrail_agent, input=user_question)
    if "block" in gr_result.final_output.lower():
        print("❌ Guardrail: BLOCKED")
        return None
    
    print("✅ Guardrail: ALLOWED")
    
    # Keyword-based routing
    user_lower = user_question.lower()
    
    # Email routing
    if any(k in user_lower for k in ["email", "send", "mail", "message", "notify"]):
        print("📧 Routing to: EMAIL AGENT")
        return email_agent
    
    # Dev routing
    if any(k in user_lower for k in ["dev", "code", "bug", "fix", "programming", "technical", "review"]):
        print("💻 Routing to: DEV AGENT")
        return dev_agent
    
    # HR routing
    if any(k in user_lower for k in ["hr", "candidate", "salary", "leave", "benefit", "recruit", "employee", "policy"]):
        print("👥 Routing to: HR AGENT")
        return hr_agent
    
    # Sales routing
    if any(k in user_lower for k in ["sales", "pitch", "product", "marketing", "customer", "revenue", "sell"]):
        print("📈 Routing to: SALES AGENT")
        return sales_agent
    
    # Manager routing
    if any(k in user_lower for k in ["manager", "approve", "document", "team", "resource", "project"]):
        print("👔 Routing to: MANAGER AGENT")
        return manager_agent
    
    # CEO routing
    if any(k in user_lower for k in ["ceo", "strategy", "strategic", "board", "direction", "vision", "investment"]):
        print("👑 Routing to: CEO AGENT")
        return ceo_agent
    
    # Default to HR
    print("👥 Default routing to: HR AGENT")
    return hr_agent


# ------------------- ATTACH GUARDRAILS TO ALL AGENTS -------------------
for agent_obj in agents:
    agent_obj.tool_input_guardrails = [reject_inappropriate_input]
    agent_obj.tool_output_guardrails = [block_inappropriate_output]


# ------------------- ORCHESTRATOR -------------------
async def company_orchestrator(user_question: str) -> str:
    """Main orchestrator for company agent system"""
    print(f"\n{'🎯 ORCHESTRATOR'.center(70,'=')}")
    print(f"📝 Input: {user_question}")
    
    # Route to appropriate agent
    agent = await dynamic_routing(user_question)
    
    if agent is None:
        return "🚨 Request blocked: Only business-related questions are allowed."
    
    # Execute agent
    print(f"\n🤖 Executing: {agent.name}")
    result = await Runner.run(agent, input=user_question)
    
    print(f"\n{'✅ COMPLETE'.center(70,'=')}")
    return result.final_output


# ------------------- MAIN -------------------
async def main():
    print("\n" + "="*70)
    print("🏢 MULTI-AGENT COMPANY SYSTEM".center(70))
    print("="*70)
    print("\n📋 AVAILABLE AGENTS:")
    print("   📧 EMAIL - Send notifications and messages")
    print("   💻 DEV - Code reviews and technical tasks")
    print("   👥 HR - Leave, salary, recruitment, benefits")
    print("   📈 SALES - Pitches, marketing, revenue")
    print("   👔 MANAGER - Approvals, team management")
    print("   👑 CEO - Strategic decisions")
    print("\n💡 Examples:")
    print("   • 'My name is John, send email to boss@company.com about leave'")
    print("   • 'Review my code for the payment module'")
    print("   • 'I need sick leave tomorrow'")
    print("   • 'Create sales pitch for our new software'")
    print("   • 'Approve the Q3 budget document'")
    print("   • 'CEO decision on market expansion'")
    print("\n" + "="*70)
    
    while True:
        try:
            user_input = input("\n❓ Your question (or 'exit'): ").strip()
            
            if user_input.lower() in ["exit", "quit"]:
                print("\n👋 Goodbye!")
                break
                
            if not user_input:
                continue
            
            response = await company_orchestrator(user_input)
            print(f"\n📢 RESPONSE:\n{response}\n")
            print("-"*70)
            
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())