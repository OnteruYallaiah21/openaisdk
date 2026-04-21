"""
Triage → **Software_Agent** (2 tools + hooks) or **General_Agent** (no tools; explains in own words).

- Software / programming / dev / APIs / infra → handoff to Software_Agent (uses tools).
- General knowledge / non-software topics → handoff to General_Agent (answers directly).

    python BasicExamples/single_software_agent_lifecycle.py

Uses ``get_model_from_config()`` (``GROQ_API_KEY`` + ``model_name`` in ``.env``).
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from llm_model_config.llm_model_config import get_model_from_config

model = get_model_from_config()
print(f"DEBUG model from get_model_from_config() model_id={getattr(model, 'model', model)!r}")

from agents import (
    Agent,
    AgentHooks,
    RunHooks,
    Runner,
    AgentHookContext,
    RunContextWrapper,
    Tool,
    function_tool,
    handoff,
)


# Groq (and some APIs) reject handoff tools whose JSON schema has ``required`` but no ``properties``.
# Pydantic ``input_type`` + ``on_handoff`` produces a valid schema (see lifecycle_hooks_14_v3.py).


class ToSoftwareHandoff(BaseModel):
    reason: str = Field(description="Why this question belongs with Software_Agent")


class ToGeneralHandoff(BaseModel):
    reason: str = Field(description="Why this question belongs with General_Agent")


async def on_handoff_to_software(ctx: RunContextWrapper[Any], data: ToSoftwareHandoff) -> None:
    print(f"DEBUG handoff callback → Software_Agent reason={data.reason!r}")


async def on_handoff_to_general(ctx: RunContextWrapper[Any], data: ToGeneralHandoff) -> None:
    print(f"DEBUG handoff callback → General_Agent reason={data.reason!r}")


# --- Software_Agent tools only ---


@function_tool
def implementation_how_to(topic: str, stack_or_constraints: str = "") -> str:
    """
    Return structured guidance on how to implement a feature or use a technology.
    Call this for software, APIs, services, libraries, or system design questions.
    """
    print(f"DEBUG tool implementation_how_to topic={topic!r} stack={stack_or_constraints!r}")
    extra = f"\nConstraints/stack noted: {stack_or_constraints}" if stack_or_constraints.strip() else ""
    return (
        f"[implementation_how_to] Topic: {topic}\n"
        "Suggested approach:\n"
        "1. Clarify requirements and interfaces (inputs/outputs, SLAs).\n"
        "2. Sketch minimal design (modules, data flow); pick boundaries.\n"
        "3. Implement core path first; add config and logging early.\n"
        "4. Add automated tests (unit + one integration); document runbooks.\n"
        "5. Roll out behind a flag; monitor; iterate.\n"
        f"{extra}"
    )


@function_tool
def software_lifecycle_notes(area: str) -> str:
    """
    Testing, CI/CD, security, observability, and delivery notes for software work.
    Use after or alongside implementation_how_to (e.g. area='testing', 'ci', 'security').
    """
    print(f"DEBUG tool software_lifecycle_notes area={area!r}")
    return (
        f"[software_lifecycle_notes] Focus: {area}\n"
        "- Testing: pyramid (unit fast, few e2e), contract tests at boundaries.\n"
        "- CI: lint + typecheck + tests on PR; trunk-based or short-lived branches.\n"
        "- Security: least privilege, secrets manager, dependency scanning, SAST optional.\n"
        "- Ops: structured logs, metrics, traces; health checks; graceful shutdown.\n"
        "- Delivery: feature flags, migrations with rollback story.\n"
    )


class AgentLevelHooks(AgentHooks):
    """Per-agent lifecycle (extends ``agents.AgentHooks`` → ``Agent(..., hooks=...)``). DEBUG prints."""

    def __init__(self, role: str) -> None:
        self.role = role
        self._turn = 0
        self._t0: float | None = None

    async def on_start(self, context: AgentHookContext[Any], agent: Agent[Any]) -> None:
        self._turn += 1
        self._t0 = time.time()
        turn_input = getattr(context, "turn_input", None)
        print(
            f"DEBUG AgentHooks.on_start role={self.role!r} agent={agent.name!r} turn={self._turn} "
            f"model={getattr(agent, 'model', None)!r}"
        )
        print(f"DEBUG AgentHooks.on_start turn_input_preview={str(turn_input)[:300]!r}")

    async def on_end(self, context: AgentHookContext[Any], agent: Agent[Any], output: Any) -> None:
        elapsed = time.time() - self._t0 if self._t0 else 0.0
        u = getattr(context, "usage", None)
        out = str(output)[:400] + ("..." if len(str(output)) > 400 else "")
        print(f"DEBUG AgentHooks.on_end role={self.role!r} agent={agent.name!r} duration_s={elapsed:.3f}")
        print(f"DEBUG AgentHooks.on_end output_preview={out!r}")
        if u:
            print(
                f"DEBUG AgentHooks.on_end usage in={u.input_tokens} out={u.output_tokens} "
                f"total={u.total_tokens} requests={u.requests}"
            )

    async def on_handoff(
        self, context: RunContextWrapper[Any], agent: Agent[Any], source: Agent[Any]
    ) -> None:
        print(
            f"DEBUG AgentHooks.on_handoff role={self.role!r} now_active={agent.name!r} from={source.name!r}"
        )

    async def on_tool_start(
        self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool
    ) -> None:
        name = getattr(tool, "name", type(tool).__name__)
        print(f"DEBUG AgentHooks.on_tool_start role={self.role!r} agent={agent.name!r} tool={name!r}")

    async def on_tool_end(
        self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool, result: str
    ) -> None:
        name = getattr(tool, "name", type(tool).__name__)
        rp = result[:250] + ("..." if len(result) > 250 else "")
        print(
            f"DEBUG AgentHooks.on_tool_end role={self.role!r} agent={agent.name!r} "
            f"tool={name!r} result_preview={rp!r}"
        )

    async def on_llm_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        system_prompt: Optional[str],
        input_items: list[Any],
    ) -> None:
        sp = (system_prompt or "")[:120]
        print(
            f"DEBUG AgentHooks.on_llm_start role={self.role!r} agent={agent.name!r} "
            f"items={len(input_items)} system_prompt_preview={sp!r}"
        )

    async def on_llm_end(
        self, context: RunContextWrapper[Any], agent: Agent[Any], response: Any
    ) -> None:
        print(
            f"DEBUG AgentHooks.on_llm_end role={self.role!r} agent={agent.name!r} "
            f"response_type={type(response).__name__!r}"
        )


class GlobalRunHooks(RunHooks):
    """Session / multi-agent lifecycle (extends ``agents.RunHooks`` → ``Runner.run(..., hooks=...)``)."""
    async def on_handoff(
        self, context: RunContextWrapper[Any], from_agent: Agent[Any], to_agent: Agent[Any]
    ) -> None:
        # SDK calls: on_handoff(context=..., from_agent=..., to_agent=...)
        print(f"DEBUG RunHooks.on_handoff from={from_agent.name!r} to={to_agent.name!r}")


# Specialists first (forward refs for handoffs)
software_agent = Agent(
    name="Software_Agent",
    instructions=(
        "You are Software_Agent. The user was routed here for a software / development question.\n"
        "1) Call implementation_how_to with the main topic (and stack_or_constraints if the user named any).\n"
        "2) Call software_lifecycle_notes with a short area string (e.g. 'testing and ci', 'security').\n"
        "3) Merge tool results into one clear, actionable answer."
    ),
    model=model,
    tools=[implementation_how_to, software_lifecycle_notes],
    hooks=AgentLevelHooks("software"),
)

general_agent = Agent(
    name="General_Agent",
    instructions=(
        "You are General_Agent. The user was routed here for a **general** (non-software) topic.\n"
        "Explain clearly in your own words: education, science concepts, history, how things work, "
        "everyday questions, etc. You have **no tools**—answer directly. Be accurate and concise."
    ),
    model=model,
    tools=[],
    hooks=AgentLevelHooks("general"),
)

triage_agent = Agent(
    name="Triage_Agent",
    instructions=(
        "You only route. Read the user's message.\n"
        "- If it is about **software or technology work**: programming, code, debugging, APIs, "
        "frameworks, databases, DevOps, architecture, or building/running systems → hand off to **Software_Agent**.\n"
        "- For **general** topics (not primarily about building software): nature, history, "
        "how something in the world works, study tips, definitions unrelated to coding → hand off to **General_Agent**.\n"
        "Do not fully answer the user yourself—always use the correct handoff.\n"
        "When calling a transfer tool, always fill in the ``reason`` field briefly."
    ),
    model=model,
    tools=[],
    handoffs=[
        handoff(software_agent, input_type=ToSoftwareHandoff, on_handoff=on_handoff_to_software),
        handoff(general_agent, input_type=ToGeneralHandoff, on_handoff=on_handoff_to_general),
    ],
    hooks=AgentLevelHooks("triage"),
)


async def run_once(user_text: str) -> str:
    print(f"\nDEBUG main Runner.run start input={user_text!r}")
    result = await Runner.run(triage_agent, input=user_text, hooks=GlobalRunHooks())
    print(f"DEBUG main Runner.run done final_output_len={len(str(result.final_output))}")
    return str(result.final_output)


async def main() -> None:
    print("Triage_Agent → Software_Agent (2 tools) OR General_Agent (direct explanation).")
    print("Lifecycle: AgentLevelHooks (per agent) + GlobalRunHooks (session). Type 'quit' to exit.\n")

    while True:
        try:
            line = input("Topic> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if not line:
            continue
        if line.lower() in ("quit", "exit", "q"):
            print("Bye.")
            break

        answer = await run_once(line)
        print(f"\n--- Answer ---\n{answer}\n")


if __name__ == "__main__":
    asyncio.run(main())
