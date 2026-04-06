import asyncio
import os
import sys
import smtplib
import time
import json
from datetime import datetime
from pathlib import Path
from email.message import EmailMessage
from typing import Optional, List, Dict, Union, Any
from pydantic import BaseModel
from collections import defaultdict
from contextlib import contextmanager

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
    Usage,
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


# ------------------- PERFORMANCE METRICS -------------------
class PerformanceMetrics:
    """Track performance metrics for all operations"""
    def __init__(self):
        self.metrics = {
            "agents": defaultdict(lambda: {"calls": 0, "total_time": 0, "avg_time": 0, "token_usage": {"input": 0, "output": 0, "total": 0, "requests": 0}}),
            "tools": defaultdict(lambda: {"calls": 0, "total_time": 0, "avg_time": 0}),
            "guardrails": defaultdict(lambda: {"calls": 0, "total_time": 0, "avg_time": 0}),
            "routing": {"calls": 0, "total_time": 0, "avg_time": 0},
        }
        self.session_start = time.time()
        self.conversation_history = []
        self.total_usage = Usage()  # Aggregate usage across all runs
        
    def update_usage(self, usage: Usage, agent_name: str):
        """Update token usage from RunContextWrapper.usage"""
        if usage:
            # Update agent-specific usage
            token_data = self.metrics["agents"][agent_name]["token_usage"]
            token_data["input"] += usage.input_tokens
            token_data["output"] += usage.output_tokens
            token_data["total"] += usage.total_tokens
            token_data["requests"] += usage.requests
            
            # Update total aggregate usage
            self.total_usage.input_tokens += usage.input_tokens
            self.total_usage.output_tokens += usage.output_tokens
            self.total_usage.total_tokens += usage.total_tokens
            self.total_usage.requests += usage.requests
            
            # Store in conversation history with detailed request entries
            self.conversation_history.append({
                "agent": agent_name,
                "timestamp": datetime.now().isoformat(),
                "usage": {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "total_tokens": usage.total_tokens,
                    "requests": usage.requests,
                }
            })
    
    def print_usage(self, usage: Usage, title: str = "Usage") -> None:
        """Print usage details in a formatted way"""
        print(f"\n{'='*50}")
        print(f"📊 {title}")
        print(f"{'='*50}")
        print(f"📥 Input tokens: {usage.input_tokens:,}")
        print(f"📤 Output tokens: {usage.output_tokens:,}")
        print(f"📊 Total tokens: {usage.total_tokens:,}")
        print(f"🔄 Requests: {usage.requests}")
        
        # Print individual request details if available
        if hasattr(usage, 'request_usage_entries') and usage.request_usage_entries:
            print(f"\n📋 Request Breakdown:")
            for i, req in enumerate(usage.request_usage_entries):
                print(f"   Request {i+1}: {req.input_tokens} input → {req.output_tokens} output")
        print(f"{'='*50}")
    
    def print_summary(self):
        """Print performance summary with actual token data"""
        print("\n" + "="*90)
        print("📊 PERFORMANCE METRICS SUMMARY".center(90))
        print("="*90)
        
        total_session_time = time.time() - self.session_start
        print(f"\n⏱️  Total Session Time: {total_session_time:.3f}s")
        
        # Print total aggregated usage
        self.print_usage(self.total_usage, "TOTAL TOKEN USAGE")
        
        # Cost estimation (GPT-4o rates ~ $2.50/1M input, $10.00/1M output)
        estimated_cost = (self.total_usage.input_tokens * 2.5 + self.total_usage.output_tokens * 10.0) / 1_000_000
        print(f"💰 Estimated Cost: ${estimated_cost:.4f} USD")
        
        # Agent Metrics with Token Details
        print(f"\n{'🤖 AGENT METRICS (WITH ACTUAL TOKENS)':^90}")
        print("-"*90)
        for agent_name, agent_data in self.metrics["agents"].items():
            if agent_data["calls"] > 0:
                tokens = agent_data["token_usage"]
                print(f"\n  📌 {agent_name}")
                print(f"     📞 Calls: {agent_data['calls']}")
                print(f"     ⏱️  Total Time: {agent_data['total_time']:.3f}s | Avg: {agent_data['avg_time']:.3f}s")
                print(f"     🔢 Tokens: {tokens['total']:,} total")
                print(f"        📥 Input: {tokens['input']:,} | 📤 Output: {tokens['output']:,}")
                print(f"        🔄 API Requests: {tokens['requests']}")
                if tokens['total'] > 0:
                    print(f"        📊 Avg Tokens/Call: {tokens['total'] / agent_data['calls']:.0f}")
        
        # Tool Metrics
        print(f"\n{'🔧 TOOL METRICS':^90}")
        print("-"*90)
        for tool_name, tool_data in self.metrics["tools"].items():
            if tool_data["calls"] > 0:
                print(f"  {tool_name}: {tool_data['calls']} calls | {tool_data['total_time']:.3f}s total | {tool_data['avg_time']:.3f}s avg")
        
        # Guardrail Metrics
        print(f"\n{'🛡️ GUARDRAIL METRICS':^90}")
        print("-"*90)
        for gr_name, gr_data in self.metrics["guardrails"].items():
            if gr_data["calls"] > 0:
                print(f"  {gr_name}: {gr_data['calls']} checks | {gr_data['total_time']:.3f}s total | {gr_data['avg_time']:.3f}s avg")
        
        # Routing Metrics
        print(f"\n{'🔀 ROUTING METRICS':^90}")
        print("-"*90)
        routing = self.metrics["routing"]
        print(f"  Calls: {routing['calls']} | Total Time: {routing['total_time']:.3f}s | Avg: {routing['avg_time']:.3f}s")
        
        print("\n" + "="*90 + "\n")
    
    def get_report(self) -> Dict:
        """Get metrics as dictionary for JSON export"""
        metrics_copy = {}
        for k, v in self.metrics.items():
            if k == "routing":
                metrics_copy[k] = v
            else:
                metrics_copy[k] = dict(v)
        return {
            "session_duration": time.time() - self.session_start,
            "total_usage": {
                "input_tokens": self.total_usage.input_tokens,
                "output_tokens": self.total_usage.output_tokens,
                "total_tokens": self.total_usage.total_tokens,
                "requests": self.total_usage.requests,
                "estimated_cost_usd": (self.total_usage.input_tokens * 2.5 + self.total_usage.output_tokens * 10.0) / 1_000_000
            },
            "metrics": metrics_copy,
            "conversation_history": self.conversation_history,
            "timestamp": datetime.now().isoformat()
        }


# Global metrics instance
metrics = PerformanceMetrics()


# ------------------- ENHANCED DEBUG HOOKS -------------------
class EnhancedDebugHooks(AgentHooks):
    """Enhanced hooks with timing and token tracking"""
    
    def __init__(self, display_name: str, metrics_instance: PerformanceMetrics):
        self.display_name = display_name
        self.counter = 0
        self.metrics = metrics_instance
        self.start_time = None
        
    async def on_start(self, context: AgentHookContext, agent: Agent) -> None:
        self.counter += 1
        self.start_time = time.time()
        
        input_data = context.turn_input if hasattr(context, 'turn_input') else None
        input_size = len(str(input_data)) if input_data else 0
        
        print(f"\n{'🟢 AGENT START'.center(80,'═')}")
        print(f"│ {self.display_name} │ Turn #{self.counter} │ {agent.name}")
        print(f"├{'─'*78}┤")
        print(f"│ ⏱️  Start Time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
        print(f"│ 📝 Input Size: {input_size} chars")
        print(f"│ 📋 Input: {str(input_data)[:150]}..." if len(str(input_data)) > 150 else f"│ 📋 Input: {input_data}")
        print(f"{'═'*80}")
        
    async def on_end(self, context: RunContextWrapper, agent: Agent, output: str) -> None:
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        # Track agent execution time
        agent_metric = self.metrics.metrics["agents"][agent.name]
        agent_metric["calls"] += 1
        agent_metric["total_time"] += elapsed
        agent_metric["avg_time"] = agent_metric["total_time"] / agent_metric["calls"]
        
        # Get actual token usage from RunContextWrapper
        usage = None
        if hasattr(context, 'usage') and context.usage:
            usage = context.usage
            self.metrics.update_usage(usage, agent.name)
        
        output_preview = output[:300] + "..." if len(output) > 300 else output
        
        print(f"\n{'🔴 AGENT END'.center(80,'═')}")
        print(f"│ {self.display_name} │ Turn #{self.counter} │ {agent.name}")
        print(f"├{'─'*78}┤")
        print(f"│ ⏱️  Duration: {elapsed:.3f}s")
        
        if usage:
            print(f"│ 🔢 ACTUAL TOKEN USAGE from RunContextWrapper:")
            print(f"│    📥 Input: {usage.input_tokens:,} tokens")
            print(f"│    📤 Output: {usage.output_tokens:,} tokens")
            print(f"│    📊 Total: {usage.total_tokens:,} tokens")
            print(f"│    🔄 API Requests: {usage.requests}")
        else:
            print(f"│ ⚠️  No usage data available")
        
        print(f"│ 💾 Output Preview: {output_preview}")
        print(f"{'═'*80}\n")


# ------------------- ENHANCED EMAIL SENDER -------------------
class EmailSender:
    """Send emails using Gmail SMTP with performance tracking"""
    
    def __init__(self, sender_email: str, app_password: str):
        self.sender_email = sender_email
        self.app_password = app_password
        
    def send_email(self, recipient_email: str, subject: str, body: str) -> bool:
        start_time = time.time()
        print(f"\n{'📧 EMAIL SEND'.center(60,'─')}")
        print(f"│ From: {self.sender_email[:20]}...")
        print(f"│ To: {recipient_email}")
        print(f"│ Subject: {subject[:50]}")
        
        try:
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            msg.set_content(body)

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(self.sender_email, self.app_password)
                smtp.send_message(msg)
            
            elapsed = time.time() - start_time
            print(f"│ ✅ Success | Duration: {elapsed:.3f}s")
            print(f"{'─'*60}")
            return True
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"│ ❌ Failed | Duration: {elapsed:.3f}s")
            print(f"│ Error: {str(e)[:100]}")
            print(f"{'─'*60}")
            return False


# ------------------- ENHANCED TOOLS WITH METRICS -------------------
@function_tool
def send_emails(sender_name: str, recipient_name: str, recipient_email: str, body: str) -> str:
    """Send email using credentials from search_user service"""
    start_time = time.time()
    print(f"\n{'🔧 TOOL EXECUTION'.center(60,'=')}")
    print(f"│ Tool: send_emails")
    print(f"│ Sender: {sender_name}")
    print(f"│ Recipient: {recipient_email}")
    
    # Use your existing search_user service
    results = search_user(sender_name)
    
    if not results:
        error_msg = f"❌ Error: No credentials found for '{sender_name}'"
        print(f"│ {error_msg}")
        print(f"{'='*60}")
        metric = metrics.metrics["tools"]["send_emails"]
        metric["calls"] += 1
        metric["total_time"] += (time.time() - start_time)
        metric["avg_time"] = metric["total_time"] / metric["calls"]
        return error_msg

    user_data = results[0]
    sender = EmailSender(
        sender_email=user_data.get("smtp_username"),
        app_password=user_data.get("smtp_password")
    )

    formatted_body = body.format(name=recipient_name) if "{name}" in body else body
    
    # Add default subject based on content
    if "late" in body.lower():
        subject = "Late for Stand-Up Meeting"
    elif "sick" in body.lower() or "leave" in body.lower():
        subject = "Leave Request"
    else:
        subject = "Company Notification"

    success = sender.send_email(
        recipient_email=recipient_email,
        subject=subject,
        body=formatted_body
    )

    result = f"✅ Email sent successfully from {sender_name} to {recipient_email}" if success else "❌ SMTP Failure. Please check App Password."
    
    metric = metrics.metrics["tools"]["send_emails"]
    metric["calls"] += 1
    metric["total_time"] += (time.time() - start_time)
    metric["avg_time"] = metric["total_time"] / metric["calls"]
    
    print(f"{'='*60}")
    return result


@function_tool
def code_review(task: str) -> str:
    """Review code or development task"""
    start_time = time.time()
    print(f"\n{'🔧 TOOL EXECUTION'.center(60,'=')}")
    print(f"│ Tool: code_review")
    print(f"│ Task: {task[:80]}...")
    time.sleep(0.05)
    
    result = f"✅ Dev team reviewed: '{task}'\n📊 Status: Code quality approved. Ready for deployment."
    
    metric = metrics.metrics["tools"]["code_review"]
    metric["calls"] += 1
    metric["total_time"] += (time.time() - start_time)
    metric["avg_time"] = metric["total_time"] / metric["calls"]
    
    print(f"{'='*60}")
    return result


@function_tool
def hr_evaluation(candidate_name: str, position: str = "") -> str:
    """Evaluate HR candidate or handle HR request"""
    start_time = time.time()
    print(f"\n{'🔧 TOOL EXECUTION'.center(60,'=')}")
    print(f"│ Tool: hr_evaluation")
    print(f"│ Candidate: {candidate_name}")
    time.sleep(0.05)
    
    if position:
        result = f"✅ HR Evaluation for {candidate_name} ({position}):\n   • Skills: Matched\n   • Experience: Verified\n   • Status: Recommended for interview"
    else:
        result = f"✅ HR evaluation completed for '{candidate_name}'. Candidate meets requirements."
    
    metric = metrics.metrics["tools"]["hr_evaluation"]
    metric["calls"] += 1
    metric["total_time"] += (time.time() - start_time)
    metric["avg_time"] = metric["total_time"] / metric["calls"]
    
    print(f"{'='*60}")
    return result


@function_tool
def sales_pitch(product: str, target_audience: str = "") -> str:
    """Create sales pitch for product"""
    start_time = time.time()
    print(f"\n{'🔧 TOOL EXECUTION'.center(60,'=')}")
    print(f"│ Tool: sales_pitch")
    print(f"│ Product: {product}")
    time.sleep(0.05)
    
    pitch = f"🚀 SALES PITCH for '{product}':\n"
    pitch += f"   • Value Proposition: Innovative solution\n"
    pitch += f"   • Key Features: Scalable, Reliable\n"
    if target_audience:
        pitch += f"   • Target: {target_audience}\n"
    
    metric = metrics.metrics["tools"]["sales_pitch"]
    metric["calls"] += 1
    metric["total_time"] += (time.time() - start_time)
    metric["avg_time"] = metric["total_time"] / metric["calls"]
    
    print(f"{'='*60}")
    return pitch


@function_tool
def manager_approval(document: str, department: str = "") -> str:
    """Approve document or request"""
    start_time = time.time()
    print(f"\n{'🔧 TOOL EXECUTION'.center(60,'=')}")
    print(f"│ Tool: manager_approval")
    print(f"│ Document: {document}")
    time.sleep(0.05)
    
    approval = f"✅ MANAGER APPROVAL for '{document}':\n   • Status: Approved\n   • Effective: Immediate"
    if department:
        approval += f"\n   • Department: {department}"
    
    metric = metrics.metrics["tools"]["manager_approval"]
    metric["calls"] += 1
    metric["total_time"] += (time.time() - start_time)
    metric["avg_time"] = metric["total_time"] / metric["calls"]
    
    print(f"{'='*60}")
    return approval


@function_tool
def ceo_decision(strategy: str, impact: str = "") -> str:
    """Make strategic CEO decision"""
    start_time = time.time()
    print(f"\n{'🔧 TOOL EXECUTION'.center(60,'=')}")
    print(f"│ Tool: ceo_decision")
    print(f"│ Strategy: {strategy}")
    time.sleep(0.05)
    
    decision = f"👔 CEO DECISION:\n   • Initiative: '{strategy}'\n   • Board Approval: Granted\n   • Implementation: Immediate"
    if impact:
        decision += f"\n   • Impact: {impact}"
    
    metric = metrics.metrics["tools"]["ceo_decision"]
    metric["calls"] += 1
    metric["total_time"] += (time.time() - start_time)
    metric["avg_time"] = metric["total_time"] / metric["calls"]
    
    print(f"{'='*60}")
    return decision


# ------------------- ENHANCED GUARDRAILS -------------------
@tool_input_guardrail
async def reject_inappropriate_input(
    data: ToolInputGuardrailData,
    agent: Agent,
) -> ToolGuardrailFunctionOutput:
    """Block inappropriate tool inputs with metrics"""
    start_time = time.time()
    
    print(f"\n{'🛡️ INPUT GUARDRAIL'.center(60,'─')}")
    print(f"│ Agent: {agent.name}")
    
    inappropriate_keywords = ["hack", "exploit", "illegal", "threat", "abuse", "password", "secret"]
    input_str = str(data.context).lower()
    
    for keyword in inappropriate_keywords:
        if keyword in input_str:
            elapsed = time.time() - start_time
            print(f"│ ❌ BLOCKED: contains '{keyword}'")
            print(f"│ Duration: {elapsed:.3f}s")
            print(f"{'─'*60}")
            
            metric = metrics.metrics["guardrails"]["input_guardrail"]
            metric["calls"] += 1
            metric["total_time"] += elapsed
            metric["avg_time"] = metric["total_time"] / metric["calls"]
            
            return ToolGuardrailFunctionOutput(
                output_info=f"Blocked inappropriate input containing '{keyword}'",
                tripwire_triggered=True,
            )
    
    elapsed = time.time() - start_time
    print(f"│ ✅ ALLOWED")
    print(f"│ Duration: {elapsed:.3f}s")
    print(f"{'─'*60}")
    
    metric = metrics.metrics["guardrails"]["input_guardrail"]
    metric["calls"] += 1
    metric["total_time"] += elapsed
    metric["avg_time"] = metric["total_time"] / metric["calls"]
    
    return ToolGuardrailFunctionOutput(
        output_info="Input allowed",
        tripwire_triggered=False,
    )


@tool_output_guardrail
async def block_inappropriate_output(
    data: ToolOutputGuardrailData,
    agent: Agent,
) -> None:
    """Block inappropriate tool outputs with metrics"""
    start_time = time.time()
    
    print(f"\n{'🛡️ OUTPUT GUARDRAIL'.center(60,'─')}")
    print(f"│ Agent: {agent.name}")
    
    sensitive_keywords = ["database password", "api key", "secret token"]
    output_str = str(data.output).lower()
    
    for keyword in sensitive_keywords:
        if keyword in output_str:
            elapsed = time.time() - start_time
            print(f"│ ❌ BLOCKED: contains '{keyword}'")
            print(f"│ Duration: {elapsed:.3f}s")
            print(f"{'─'*60}")
            
            metric = metrics.metrics["guardrails"]["output_guardrail"]
            metric["calls"] += 1
            metric["total_time"] += elapsed
            metric["avg_time"] = metric["total_time"] / metric["calls"]
            
            raise ToolOutputGuardrailTripwireTriggered(
                f"Output blocked: contains sensitive keyword '{keyword}'"
            )
    
    elapsed = time.time() - start_time
    print(f"│ ✅ ALLOWED")
    print(f"│ Duration: {elapsed:.3f}s")
    print(f"{'─'*60}")
    
    metric = metrics.metrics["guardrails"]["output_guardrail"]
    metric["calls"] += 1
    metric["total_time"] += elapsed
    metric["avg_time"] = metric["total_time"] / metric["calls"]


# ------------------- CREATE AGENTS -------------------
agents = []

# Email Agent
email_agent = Agent(
    name="Email Agent",
    instructions="""Handle user requests to send emails.
    
    CRITICAL: Extract recipient's name from context.
    
    Steps:
    1. Extract sender's name (look for "My name is X" or "from X")
    2. Extract recipient's name (look for "to X" or "manager X")
    3. Extract recipient's email address
    4. Extract the message content
    5. Call send_emails tool with all extracted information
    
    If any information is missing, ask the user politely for it.""",
    tools=[send_emails],
    model=model,
    hooks=EnhancedDebugHooks("📧 EMAIL", metrics),
)
agents.append(email_agent)

# Dev Agent
dev_agent = Agent(
    name="Dev Agent",
    instructions="Handle development-related tasks using code_review tool.",
    tools=[code_review],
    model=model,
    hooks=EnhancedDebugHooks("💻 DEV", metrics),
)
agents.append(dev_agent)

# HR Agent
hr_agent = Agent(
    name="HR Agent",
    instructions="Handle HR-related tasks using hr_evaluation tool.",
    tools=[hr_evaluation],
    model=model,
    hooks=EnhancedDebugHooks("👥 HR", metrics),
)
agents.append(hr_agent)

# Sales Agent
sales_agent = Agent(
    name="Sales Agent",
    instructions="Handle sales-related tasks using sales_pitch tool.",
    tools=[sales_pitch],
    model=model,
    hooks=EnhancedDebugHooks("📈 SALES", metrics),
)
agents.append(sales_agent)

# Manager Agent
manager_agent = Agent(
    name="Manager Agent",
    instructions="Handle management tasks using manager_approval tool.",
    tools=[manager_approval],
    model=model,
    hooks=EnhancedDebugHooks("👔 MANAGER", metrics),
)
agents.append(manager_agent)

# CEO Agent
ceo_agent = Agent(
    name="CEO Agent",
    instructions="Handle strategic decisions using ceo_decision tool.",
    tools=[ceo_decision],
    model=model,
    hooks=EnhancedDebugHooks("👑 CEO", metrics),
)
agents.append(ceo_agent)

# Guardrail Agent
guardrail_agent = Agent(
    name="Guardrail Agent",
    instructions="""You are a security guardrail.
    Respond ONLY with 'allow' for ANY business-related questions.
    Respond with 'block' ONLY for profanity, illegal activities, or completely non-business questions.
    Just say 'allow' or 'block' - nothing else.""",
    model=model,
    hooks=EnhancedDebugHooks("🛡️ GUARDRAIL", metrics),
)


# ------------------- ENHANCED ROUTING -------------------
class RoutingRequest(BaseModel):
    user_question: str
    suggested_agent: Optional[str] = None
    routing_time: float = 0.0


async def dynamic_routing(user_question: str) -> Optional[Agent]:
    """Route user question to appropriate agent with metrics"""
    start_time = time.time()
    
    print(f"\n{'🔀 ROUTING DECISION'.center(80,'═')}")
    print(f"│ Question: {user_question[:80]}...")
    
    # First check guardrail
    gr_result = await Runner.run(guardrail_agent, input=user_question)
    if "block" in gr_result.final_output.lower():
        elapsed = time.time() - start_time
        print(f"│ ❌ Guardrail: BLOCKED")
        print(f"│ Duration: {elapsed:.3f}s")
        print(f"{'═'*80}")
        
        routing_metric = metrics.metrics["routing"]
        routing_metric["calls"] += 1
        routing_metric["total_time"] += elapsed
        routing_metric["avg_time"] = routing_metric["total_time"] / routing_metric["calls"]
        
        return None
    
    print(f"│ ✅ Guardrail: ALLOWED")
    
    # Keyword-based routing with priority
    user_lower = user_question.lower()
    routing_map = [
        (["email", "send", "mail", "message", "notify"], "📧 EMAIL AGENT", email_agent),
        (["dev", "code", "bug", "fix", "programming", "technical", "review"], "💻 DEV AGENT", dev_agent),
        (["hr", "candidate", "salary", "leave", "benefit", "recruit", "employee", "policy"], "👥 HR AGENT", hr_agent),
        (["sales", "pitch", "product", "marketing", "customer", "revenue", "sell"], "📈 SALES AGENT", sales_agent),
        (["manager", "approve", "document", "team", "resource", "project"], "👔 MANAGER AGENT", manager_agent),
        (["ceo", "strategy", "strategic", "board", "direction", "vision", "investment"], "👑 CEO AGENT", ceo_agent),
    ]
    
    selected_agent = hr_agent
    selected_display = "👥 HR AGENT"
    
    for keywords, display, agent in routing_map:
        if any(k in user_lower for k in keywords):
            selected_agent = agent
            selected_display = display
            break
    
    elapsed = time.time() - start_time
    print(f"│ 🎯 Routed to: {selected_display}")
    print(f"│ Duration: {elapsed:.3f}s")
    print(f"{'═'*80}")
    
    routing_metric = metrics.metrics["routing"]
    routing_metric["calls"] += 1
    routing_metric["total_time"] += elapsed
    routing_metric["avg_time"] = routing_metric["total_time"] / routing_metric["calls"]
    
    return selected_agent


# ------------------- ATTACH GUARDRAILS TO ALL AGENTS -------------------
for agent_obj in agents:
    agent_obj.tool_input_guardrails = [reject_inappropriate_input]
    agent_obj.tool_output_guardrails = [block_inappropriate_output]


# ------------------- ENHANCED ORCHESTRATOR -------------------
async def company_orchestrator(user_question: str) -> str:
    """Main orchestrator for company agent system with full metrics"""
    print(f"\n{'🎯 ORCHESTRATOR START'.center(80,'█')}")
    print(f"█ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"█ Question: {user_question}")
    print(f"{'█'*80}")
    
    # Route to appropriate agent
    agent = await dynamic_routing(user_question)
    
    if agent is None:
        error_msg = "🚨 Request blocked: Only business-related questions are allowed."
        print(f"\n❌ {error_msg}")
        return error_msg
    
    # Execute agent
    print(f"\n{'🤖 EXECUTING AGENT'.center(80,'─')}")
    result = await Runner.run(agent, input=user_question)
    
    # Print usage from the run context
    if hasattr(result, 'context_wrapper') and result.context_wrapper:
        metrics.print_usage(result.context_wrapper.usage, f"USAGE FOR {agent.name}")
    
    print(f"\n{'✅ ORCHESTRATOR COMPLETE'.center(80,'█')}")
    return result.final_output


# ------------------- MAIN -------------------
async def main():
    print("\n" + "█"*80)
    print("🏢 MULTI-AGENT COMPANY SYSTEM WITH TOKEN TRACKING".center(80))
    print("█"*80)
    print("\n📊 FEATURES:")
    print("   ⏱️  Real-time performance metrics")
    print("   🔢 ACTUAL token consumption from RunContextWrapper.usage")
    print("   💰 Cost estimation based on GPT-4o rates")
    print("   📈 Agent/tool execution timing")
    print("   🛡️ Input/output guardrails")
    print("   🎯 Smart routing with priority")
    print("\n📋 AVAILABLE AGENTS:")
    print("   📧 EMAIL - Send notifications and messages")
    print("   💻 DEV - Code reviews and technical tasks")
    print("   👥 HR - Leave, salary, recruitment, benefits")
    print("   📈 SALES - Pitches, marketing, revenue")
    print("   👔 MANAGER - Approvals, team management")
    print("   👑 CEO - Strategic decisions")
    print("\n💡 EXAMPLES:")
    print("   • 'My name is Yallaiah, send email to Preethi at rpreethi1104@gmail.com saying I will be 15 minutes late'")
    print("   • 'Review my code for the payment module'")
    print("   • 'I need sick leave tomorrow'")
    print("   • 'Create sales pitch for our new software'")
    print("\n" + "█"*80)
    
    while True:
        try:
            user_input = input("\n❓ Your question (or 'exit' for summary): ").strip()
            
            if user_input.lower() in ["exit", "quit"]:
                metrics.print_summary()
                
                save = input("\n💾 Save metrics to file? (y/n): ").strip().lower()
                if save == 'y':
                    filename = f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    with open(filename, 'w') as f:
                        json.dump(metrics.get_report(), f, indent=2)
                    print(f"✅ Metrics saved to {filename}")
                
                print("\n👋 Goodbye!")
                break
                
            if not user_input:
                continue
            
            response = await company_orchestrator(user_input)
            print(f"\n{'📢 FINAL RESPONSE'.center(80,'═')}")
            print(f"{response}")
            print("═"*80)
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Interrupted!")
            metrics.print_summary()
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())