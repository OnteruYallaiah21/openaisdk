import asyncio
import sys
import time
import datetime
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field

# 1. SETUP MODEL CONFIG
basepath = Path(__file__).resolve().parent.parent
sys.path.append(str(basepath))
from llm_model_config.llm_model_config import ModelSingleton
model = ModelSingleton.get_instance()

from agents import (
    Agent, Runner, RunContextWrapper, AgentHooks, RunHooks,
    AgentHookContext, function_tool, Tool, handoff
)

# ============================================================
# SHARED BUSINESS STATE  (single source of truth for the run)
# ============================================================
class RefundCase(BaseModel):
    case_id:          str   = "CASE-2024-0042"
    order_id:         str   = "ORD-9981"
    user_id:          str   = "USR-441"
    user_name:        str   = "Yallaiah"
    refund_amount:    float = 150.0
    customer_tier:    str   = "UNKNOWN"   # populated by lookup_order
    status:           str   = "INITIATED"
    fraud_score:      float = 0.0         # 0-100, populated by check_fraud_score
    within_window:    bool  = False       # populated by verify_return_window
    refund_approved:  bool  = False
    notification_sent: bool = False
    audit_log:        list  = Field(default_factory=list)
    tool_call_count:  int   = 0
    agent_timers:     dict  = Field(default_factory=dict)  # agent_name -> start_time
    sla_seconds:      float = 30.0        # SLA: entire run must complete < 30s

# ============================================================
# AUDIT HELPER  (writes to in-memory log on the state object)
# ============================================================
def audit(ctx: RunContextWrapper, actor: str, event: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    entry = f"[{ts}] {actor}: {event}"
    ctx.context.audit_log.append(entry)
    print(f"      📋 AUDIT → {entry}")

# ============================================================
# GLOBAL RUN HOOKS  — system-level, fires for every agent
# ============================================================
class GlobalMonitor(RunHooks):

    async def on_agent_start(self, context: AgentHookContext, agent: Agent):
        state = context.context
        state.agent_timers[agent.name] = time.time()
        state.status = f"ACTIVE:{agent.name}"
        print("\n" + "═"*70)
        print(f"🌍 [GLOBAL] ▶ SESSION START  |  Agent: {agent.name}")
        print(f"   Case: {state.case_id}  |  Amount: ${state.refund_amount}")
        print(f"   Current Status: {state.status}")
        print("═"*70)

    async def on_handoff(self, context: RunContextWrapper, from_agent: Agent, to_agent: Agent):
        state = context.context
        elapsed = time.time() - state.agent_timers.get(from_agent.name, time.time())
        print(f"\n🌍 [GLOBAL] 🔄 HANDOFF DETECTED")
        print(f"   Route : {from_agent.name} ──► {to_agent.name}")
        print(f"   {from_agent.name} ran for {elapsed:.2f}s")
        print(f"   Fraud Score at handoff: {state.fraud_score}")
        print(f"   Case Status: {state.status}")
        # SLA check on handoff leg
        total_elapsed = time.time() - min(state.agent_timers.values())
        if total_elapsed > state.sla_seconds * 0.75:
            print(f"   ⚠️  SLA WARNING: {total_elapsed:.1f}s used of {state.sla_seconds}s budget!")

    async def on_agent_end(self, context: AgentHookContext, agent: Agent, output: Any):
        state = context.context
        total_elapsed = time.time() - min(state.agent_timers.values()) if state.agent_timers else 0
        print("\n" + "═"*70)
        print(f"🌍 [GLOBAL] ■ SESSION END")
        print(f"   Final Status      : {state.status}")
        print(f"   Refund Approved   : {state.refund_approved}")
        print(f"   Notification Sent : {state.notification_sent}")
        print(f"   Total Tool Calls  : {state.tool_call_count}")
        print(f"   Total Run Time    : {total_elapsed:.2f}s")
        if total_elapsed > state.sla_seconds:
            print(f"   ❌ SLA BREACHED! Exceeded {state.sla_seconds}s")
        else:
            print(f"   ✅ SLA OK (budget: {state.sla_seconds}s)")
        print("\n   📋 FULL AUDIT TRAIL:")
        for entry in state.audit_log:
            print(f"      {entry}")
        print("═"*70)

# ============================================================
# AGENT-SPECIFIC HOOKS  — attached to individual agents
# ============================================================
class SpecialistHooks(AgentHooks):

    async def on_start(self, context: AgentHookContext, agent: Agent):
        state = context.context
        print(f"\n--- [👤 START] {agent.name} | Status={state.status} ---")
        # Precondition check: if fraud score is critical, warn immediately
        if state.fraud_score >= 80:
            print(f"   🚨 HIGH FRAUD RISK ({state.fraud_score}) — agent must proceed carefully!")

    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool):
        state = context.context
        state.tool_call_count += 1
        print(f"\n--- [👤 TOOL▶] {agent.name} → {tool.name}  (call #{state.tool_call_count}) ---")
        # Rate limit: hard stop at 15 tool calls to prevent runaway agents
        if state.tool_call_count > 15:
            raise RuntimeError(f"RATE LIMIT: {agent.name} exceeded 15 tool calls. Aborting.")

    async def on_tool_end(self, context: RunContextWrapper, agent: Agent, tool: Tool, result: str):
        state = context.context
        print(f"--- [👤 TOOL■] {tool.name} returned → {str(result)[:80]} ---")
        # Auto-flag if fraud score spiked after tool
        if tool.name == "check_fraud_score" and state.fraud_score >= 70:
            print(f"   🚨 FRAUD ALERT: score={state.fraud_score} — routing may be affected!")
            audit(context, "FraudEngine", f"HIGH FRAUD SCORE {state.fraud_score} flagged after tool call")

    async def on_handoff(self, context: RunContextWrapper, agent: Agent, source: Agent):
        state = context.context
        print(f"\n--- [👤 HANDOFF] {source.name} ──► {agent.name} ---")
        audit(context, "Router", f"Control transferred {source.name} → {agent.name}, status={state.status}")

    async def on_end(self, context: AgentHookContext, agent: Agent, output: Any):
        state = context.context
        elapsed = time.time() - state.agent_timers.get(agent.name, time.time())
        print(f"\n--- [👤 END] {agent.name} finished in {elapsed:.2f}s | Status={state.status} ---")
        audit(context, agent.name, f"Agent completed. refund_approved={state.refund_approved}")

# ============================================================
# TOOLS  (dummy data simulating real backend calls)
# ============================================================

@function_tool
async def lookup_order(ctx: RunContextWrapper, order_id: str) -> str:
    """Fetch order details from the orders database."""
    audit(ctx, "OrderDB", f"Fetching order {order_id}")
    # Dummy response simulating DB record
    ORDERS = {
        "ORD-9981": {"product": "Wireless Headphones", "amount": 150.0,
                     "purchased_days_ago": 12, "customer_tier": "GOLD", "payment": "CREDIT_CARD"},
        "ORD-1234": {"product": "USB Cable", "amount": 9.99,
                     "purchased_days_ago": 45, "customer_tier": "BRONZE", "payment": "PAYPAL"},
    }
    order = ORDERS.get(order_id, {"error": "Order not found"})
    if "error" not in order:
        ctx.context.customer_tier = order["customer_tier"]
    return str(order)


@function_tool
async def verify_return_window(ctx: RunContextWrapper, order_id: str) -> str:
    """Check if the order is within the 30-day return window."""
    audit(ctx, "ReturnPolicy", f"Checking return window for {order_id}")
    # Dummy: ORD-9981 purchased 12 days ago → within window
    DAYS_MAP = {"ORD-9981": 12, "ORD-1234": 45}
    days_ago = DAYS_MAP.get(order_id, 999)
    within = days_ago <= 30
    ctx.context.within_window = within
    status = "ELIGIBLE" if within else "EXPIRED"
    return f"Order {order_id} purchased {days_ago} days ago → Return window: {status}"


@function_tool
async def check_fraud_score(ctx: RunContextWrapper, user_id: str, amount: float) -> str:
    """Run fraud detection model against the user and transaction amount."""
    audit(ctx, "FraudEngine", f"Scoring user={user_id} amount=${amount}")
    # Dummy scoring: high amounts on new users score higher
    SCORES = {"USR-441": 22.0, "USR-999": 87.5, "USR-100": 5.0}
    score = SCORES.get(user_id, 50.0)
    ctx.context.fraud_score = score
    risk = "LOW" if score < 40 else "MEDIUM" if score < 70 else "HIGH"
    return f"Fraud score for {user_id}: {score}/100 — Risk Level: {risk}"


@function_tool
async def get_tier_benefits(ctx: RunContextWrapper, user_id: str) -> str:
    """Look up customer tier and special refund policies for this user."""
    audit(ctx, "LoyaltyDB", f"Fetching tier benefits for {user_id}")
    BENEFITS = {
        "GOLD":   {"instant_refund": True,  "max_auto_approve": 500.0, "priority_support": True},
        "SILVER": {"instant_refund": False, "max_auto_approve": 200.0, "priority_support": False},
        "BRONZE": {"instant_refund": False, "max_auto_approve": 50.0,  "priority_support": False},
    }
    tier = ctx.context.customer_tier
    benefits = BENEFITS.get(tier, BENEFITS["BRONZE"])
    return f"Tier={tier}, Benefits={benefits}"


@function_tool
async def process_refund(ctx: RunContextWrapper, order_id: str, amount: float, method: str) -> str:
    """Execute the refund via the payment gateway."""
    audit(ctx, "PaymentGateway", f"Processing ${amount} refund for {order_id} via {method}")
    if ctx.context.fraud_score >= 80:
        ctx.context.status = "REFUND_BLOCKED_FRAUD"
        return f"BLOCKED: Refund denied — fraud score {ctx.context.fraud_score} exceeds threshold."
    if not ctx.context.within_window:
        ctx.context.status = "REFUND_BLOCKED_WINDOW"
        return f"BLOCKED: Order {order_id} is outside the 30-day return window."
    # Dummy: simulate payment gateway success
    ctx.context.refund_approved = True
    ctx.context.status = "REFUND_PROCESSED"
    txn_id = f"TXN-{int(time.time())}"
    audit(ctx, "PaymentGateway", f"Refund SUCCESS txn_id={txn_id}")
    return f"SUCCESS: ${amount} refunded via {method}. Transaction ID: {txn_id}"


@function_tool
async def send_notification(ctx: RunContextWrapper, channel: str, message: str) -> str:
    """Send email/SMS/push notification to the customer."""
    audit(ctx, "NotificationService", f"Sending via {channel}: {message[:40]}...")
    # Dummy: simulate send
    ctx.context.notification_sent = True
    ctx.context.status = "NOTIFIED"
    return f"Notification sent via {channel} to {ctx.context.user_name}. ✓"


@function_tool
async def log_compliance_record(ctx: RunContextWrapper, decision: str, justification: str) -> str:
    """Write a compliance/audit record to the regulatory log for refunds > $100."""
    audit(ctx, "ComplianceSystem", f"Recording decision={decision}")
    record = {
        "case_id":       ctx.context.case_id,
        "order_id":      ctx.context.order_id,
        "amount":        ctx.context.refund_amount,
        "decision":      decision,
        "justification": justification,
        "fraud_score":   ctx.context.fraud_score,
        "timestamp":     datetime.datetime.now().isoformat(),
    }
    return f"Compliance record written: {record}"


@function_tool
async def transfer_to_refund_agent(ctx: RunContextWrapper, reason: str) -> str:
    """Route the validated case to the Refund Processor agent."""
    audit(ctx, "Router", f"Routing to Refund_Agent: {reason}")
    ctx.context.status = "ROUTED_TO_REFUND"
    return refund_agent   # SDK sees this as a handoff trigger


@function_tool
async def transfer_to_manager(ctx: RunContextWrapper, reason: str) -> str:
    """Escalate this refund case to a human manager for manual review."""
    audit(ctx, "Escalation", f"Escalating to manager: {reason}")
    ctx.context.status = "ESCALATED_TO_MANAGER"
    return manager_agent   # SDK sees this as a handoff trigger


# ============================================================
# AGENTS
# ============================================================

# Forward-declare so triage_agent can reference it in tools list
manager_agent: Agent   # defined below

manager_agent = Agent(
    name="Manager_Agent",
    instructions="""
    You are the Senior Refund Manager. You handle escalated high-value cases.
    Steps:
    1. Call log_compliance_record with decision='MANAGER_APPROVED' and your justification.
    2. Call process_refund to execute the refund.
    3. Call send_notification via 'EMAIL' informing the customer of approval.
    4. End with: 'Case closed by Manager — Refund complete.'
    """,
    model=model,
    tools=[process_refund, send_notification, log_compliance_record],
    hooks=SpecialistHooks()
)

fraud_review_agent = Agent(
    name="Fraud_Review_Agent",
    instructions="""
    You are the Fraud Analyst. A suspicious transaction was flagged.
    Steps:
    1. Call log_compliance_record with decision='FRAUD_HOLD' and details.
    2. Call send_notification via 'SMS' to tell the customer their request is under review.
    3. End with: 'Fraud review initiated — case on hold.'
    """,
    model=model,
    tools=[send_notification, log_compliance_record],
    hooks=SpecialistHooks()
)

refund_agent = Agent(
    name="Refund_Agent",
    instructions="""
    You are the Refund Processor.
    Steps:
    1. Call process_refund with the order_id, refund_amount, and payment method 'CREDIT_CARD'.
    2. If refund SUCCESS, call send_notification via 'EMAIL' to confirm.
    3. If refund BLOCKED, call transfer_to_manager with the reason.
    4. End with a summary.
    """,
    model=model,
    tools=[process_refund, send_notification, transfer_to_manager],
    hooks=SpecialistHooks()
)

triage_agent = Agent(
    name="Triage_Agent",
    instructions="""
    You are the Support Triage Agent. Assess and route the refund request.
    Execute ALL steps in order:
    1. Call lookup_order with the order_id from context (ORD-9981).
    2. Call verify_return_window to check eligibility.
    3. Call check_fraud_score with user_id (USR-441) and refund_amount (150.0).
    4. Call get_tier_benefits with user_id (USR-441).
    5. Routing decision:
       - If fraud_score >= 70 → call transfer_to_manager with reason 'HIGH_FRAUD_RISK'
       - Else if refund_amount > 100 → call transfer_to_refund_agent with reason 'ELIGIBLE_HIGH_VALUE'
       - Else → call transfer_to_refund_agent with reason 'ELIGIBLE_STANDARD'
    End with your routing decision summary.
    """,
    model=model,
    tools=[
        lookup_order,
        verify_return_window,
        check_fraud_score,
        get_tier_benefits,
        transfer_to_refund_agent,
        transfer_to_manager,
    ],
    hooks=SpecialistHooks()
)

# ============================================================
# MAIN
# ============================================================
async def main():
    state = RefundCase(refund_amount=150.0)

    print("🚀 E-COMMERCE REFUND PIPELINE — LIFECYCLE HOOKS DEMO")
    print(f"   Case  : {state.case_id}")
    print(f"   Order : {state.order_id}  |  User: {state.user_name}")
    print(f"   Amount: ${state.refund_amount}\n")

    await Runner.run(
        triage_agent,
        input=(
            f"Process refund for order {state.order_id}. "
            f"User {state.user_id} is requesting ${state.refund_amount} back."
        ),
        context=state,
        hooks=GlobalMonitor()
    )

if __name__ == "__main__":
    asyncio.run(main())
