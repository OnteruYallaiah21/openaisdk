"""
Three-agent demo: coordinator -> research -> writer, with verbose tracing.

Inspired by lifecycle_with_llm_as_guraddril_usage_2_w_v3.py (AgentHooks, metrics-style
logging) and lifecycle_hooks_14_v3.py (handoff(), RunHooks.on_handoff).

Run from repo root (or ensure parent is on PYTHONPATH):
    python BasicExamples/three_agent_trace_handoff_demo.py

Uses ``get_model_from_config()`` (``GROQ_API_KEY`` + ``model_name`` in ``.env``); optional ``model=`` override.

Debug style: plain ``print(f"DEBUG ...")`` lines (no banner boxes).

Where console output comes from
---------------------------------
* ``AgentLevelHooks`` — **subclass of** ``agents.AgentHooks`` (per-agent), wired on each ``Agent(..., hooks=...)``.
  Fires: ``on_start``, ``on_end``, ``on_handoff``, ``on_tool_start`` / ``on_tool_end``, ``on_llm_start`` / ``on_llm_end``.
* ``GlobalRunHooks`` — **subclass of** ``agents.RunHooks`` (session / multi-agent), wired on ``Runner.run(..., hooks=...)``.
  Fires: ``on_agent_start`` / ``on_agent_end``, ``on_handoff``, ``on_tool_start`` / ``on_tool_end`` (run-wide).
* **Tool bodies** — plain Python inside ``@function_tool`` functions (not hook classes).
* **``handoff(..., on_handoff=...)``** — async callbacks ``on_to_research`` / ``on_to_writer`` (not hook classes).
* **``log_agent_configuration``** — module helper for static agent config dumps.

See also: ``BasicExamples/agents_sdk_context_reference.md`` for **RunContextWrapper**,
**AgentHookContext**, and **Usage** fields you can read in hooks and callbacks.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel, Field

# ------------------- PATH + MODEL (same pattern as lifecycle_with_llm..._v3.py) -------------------
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from llm_model_config.llm_model_config import get_model_from_config

# Uses .env GROQ_API_KEY + model_name. Override, e.g.: get_model_from_config(model="openai/gpt-oss-20b")
model = get_model_from_config()
print(f"DEBUG get_model_from_config model_id={getattr(model, 'model', model)!r}")

from agents import (
    Agent,
    AgentHooks,
    RunHooks,
    Runner,
    RunContextWrapper,
    AgentHookContext,
    Tool,
    function_tool,
    handoff,
)


# ------------------- DEBUG: simple print(f"...") only -------------------
def describe_model(m: Any) -> str:
    if m is None:
        return "(none)"
    if isinstance(m, str):
        return m
    mid = getattr(m, "model", None) or getattr(m, "model_id", None)
    cls = type(m).__name__
    if mid:
        return f"{cls}(model={mid!r})"
    return f"{cls}({m!r})"


def log_agent_configuration(agent: Agent[Any], *, label: str = "AGENT CONFIG") -> None:
    """Print instructions, model, tools, and handoffs for one agent.

    NOTE: This is a normal module-level helper — not AgentHooks nor RunHooks.
    """
    tool_names: List[str] = []
    for t in agent.tools or []:
        name = getattr(t, "name", None) or type(t).__name__
        tool_names.append(str(name))

    handoff_summaries: List[str] = []
    for h in agent.handoffs or []:
        target = getattr(h, "agent_name", None) or getattr(h, "tool_name", None) or repr(h)
        handoff_summaries.append(str(target))

    print(f"\nDEBUG log_agent_configuration() [{label}] agent={agent.name!r} (not hooks)")
    print(f"  model={describe_model(getattr(agent, 'model', None))}")
    print(f"  tools={tool_names or '(none)'}  handoffs={handoff_summaries or '(none)'}")
    print(f"  instructions:\n{(agent.instructions or '').strip() or '(empty)'}")


@dataclass
class TraceJournal:
    """Lightweight in-memory trace (optional JSON dump)."""
    events: List[dict] = field(default_factory=list)

    def add(self, kind: str, **payload: Any) -> None:
        row = {"ts": datetime.now().isoformat(), "kind": kind, **payload}
        self.events.append(row)
        preview = json.dumps(row, default=str)[:500]
        print(f"DEBUG journal {preview}")


journal = TraceJournal()


# ------------------- TOOLS (each prints a visible tool trace) -------------------
@function_tool
def coordinator_checkpoint(note: str) -> str:
    """Log a short coordinator note before delegating work."""
    print(f"DEBUG @function_tool coordinator_checkpoint note={note!r}")
    journal.add("tool", tool="coordinator_checkpoint", note=note)
    return f"checkpoint recorded: {note}"


@function_tool
def fetch_topic_facts(topic: str) -> str:
    """Return concise factual bullets for a topic (demo stub, no web)."""
    print(f"DEBUG @function_tool fetch_topic_facts topic={topic!r}")
    body = (
        f"Facts for {topic!r}:\n"
        "- asyncio runs coroutines on an event loop\n"
        "- async/await avoids blocking threads for I/O\n"
        "- gather() runs tasks concurrently\n"
    )
    journal.add("tool", tool="fetch_topic_facts", topic=topic)
    return body


@function_tool
def finalize_brief(markdown_draft: str) -> str:
    """Polish research notes into a short brief."""
    preview = markdown_draft.strip().replace("\n", " ")[:200]
    print(f"DEBUG @function_tool finalize_brief draft_preview={preview!r}...")
    journal.add("tool", tool="finalize_brief", draft_chars=len(markdown_draft))
    return (
        "## Brief\n\n"
        + markdown_draft.strip()
        + "\n\n*(demo: writer tool applied minimal formatting)*\n"
    )


# ------------------- HANDOFF PAYLOADS -------------------
class ToResearchHandoff(BaseModel):
    """Arguments for transfer_to_research_agent."""

    reason: str = Field(description="Why the coordinator is handing off to research")


class ToWriterHandoff(BaseModel):
    """Arguments for transfer_to_writer_agent."""

    reason: str = Field(description="Why research is handing off to the writer")
    key_points: str = Field(
        description="Compressed facts or bullets the writer should turn into the final brief"
    )


async def on_to_research(ctx: RunContextWrapper[Any], data: ToResearchHandoff) -> None:
    print(f"DEBUG handoff on_to_research reason={data.reason!r}")
    journal.add("handoff_callback", leg="coordinator->research", reason=data.reason)


async def on_to_writer(ctx: RunContextWrapper[Any], data: ToWriterHandoff) -> None:
    kp = data.key_points[:300] + ("..." if len(data.key_points) > 300 else "")
    print(f"DEBUG handoff on_to_writer reason={data.reason!r} key_points={kp!r}")
    journal.add(
        "handoff_callback",
        leg="research->writer",
        reason=data.reason,
        key_points_preview=data.key_points[:200],
    )


# ------------------- HOOKS: agent-level + run-level -------------------
# All debug lines start with "DEBUG " — filter with:  rg '^DEBUG '  or  grep DEBUG
#   • AgentLevelHooks  — AgentHooks  → Agent(..., hooks=...)  [per-agent]
#   • GlobalRunHooks   — RunHooks    → Runner.run(..., hooks=...)  [session / multi-agent]
#   • @function_tool     — tool body when the model calls the tool
#   • on_to_research / on_to_writer — handoff(..., on_handoff=...) callbacks


class AgentLevelHooks(AgentHooks):
    """Per-agent lifecycle (extends ``agents.AgentHooks``). DEBUG via ``print(f\"DEBUG ...\")``."""

    def __init__(self, tag: str):
        self.tag = tag
        self._turn = 0
        self._t0: float | None = None

    async def on_start(self, context: AgentHookContext[Any], agent: Agent[Any]) -> None:
        self._turn += 1
        self._t0 = time.time()
        inp = getattr(context, "turn_input", None)
        tin = str(inp)[:400] + ("..." if inp and len(str(inp)) > 400 else "")
        print(
            f"DEBUG AgentHooks.on_start tag={self.tag!r} agent={agent.name!r} "
            f"turn={self._turn} model={describe_model(getattr(agent, 'model', None))!r}"
        )
        print(f"DEBUG AgentHooks.on_start turn_input={tin!r}")
        journal.add("agent_start", tag=self.tag, agent=agent.name)

    async def on_end(self, context: AgentHookContext[Any], agent: Agent[Any], output: Any) -> None:
        elapsed = time.time() - self._t0 if self._t0 else 0.0
        usage = getattr(context, "usage", None)
        out_preview = str(output)[:400] + ("..." if len(str(output)) > 400 else "")
        print(
            f"DEBUG AgentHooks.on_end tag={self.tag!r} agent={agent.name!r} "
            f"duration_s={elapsed:.3f} output_preview={out_preview!r}"
        )
        if usage:
            print(
                f"DEBUG AgentHooks.on_end usage in={usage.input_tokens} out={usage.output_tokens} "
                f"total={usage.total_tokens} requests={usage.requests}"
            )
        journal.add("agent_end", tag=self.tag, agent=agent.name, seconds=elapsed)

    async def on_handoff(
        self, context: RunContextWrapper[Any], agent: Agent[Any], source: Agent[Any]
    ) -> None:
        print(
            f"DEBUG AgentHooks.on_handoff tag={self.tag!r} now_active={agent.name!r} "
            f"from={source.name!r}"
        )
        journal.add("agent_hook_handoff", tag=self.tag, agent=agent.name, from_agent=source.name)

    async def on_tool_start(
        self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool
    ) -> None:
        name = getattr(tool, "name", type(tool).__name__)
        print(f"DEBUG AgentHooks.on_tool_start tag={self.tag!r} agent={agent.name!r} tool={name!r}")
        journal.add("tool_start", tag=self.tag, agent=agent.name, tool=name)

    async def on_tool_end(
        self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool, result: str
    ) -> None:
        name = getattr(tool, "name", type(tool).__name__)
        rp = result[:300] + ("..." if len(result) > 300 else "")
        print(
            f"DEBUG AgentHooks.on_tool_end tag={self.tag!r} agent={agent.name!r} "
            f"tool={name!r} result={rp!r}"
        )
        journal.add("tool_end", tag=self.tag, agent=agent.name, tool=name)

    async def on_llm_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        system_prompt: Optional[str],
        input_items: list[Any],
    ) -> None:
        sp = (system_prompt or "")[:200] + ("..." if system_prompt and len(system_prompt) > 200 else "")
        print(
            f"DEBUG AgentHooks.on_llm_start tag={self.tag!r} agent={agent.name!r} "
            f"input_items={len(input_items)} system_prompt_preview={sp!r}"
        )
        journal.add("llm_start", tag=self.tag, agent=agent.name, items=len(input_items))

    async def on_llm_end(
        self, context: RunContextWrapper[Any], agent: Agent[Any], response: Any
    ) -> None:
        print(
            f"DEBUG AgentHooks.on_llm_end tag={self.tag!r} agent={agent.name!r} "
            f"response_type={type(response).__name__!r}"
        )
        journal.add("llm_end", tag=self.tag, agent=agent.name)


class GlobalRunHooks(RunHooks):
    """Session / multi-agent lifecycle (extends ``agents.RunHooks`` → ``Runner.run(..., hooks=...)``)."""

    async def on_agent_start(self, context: AgentHookContext[Any], agent: Agent[Any]) -> None:
        print(f"DEBUG RunHooks.on_agent_start agent={agent.name!r}")
        journal.add("run_agent_start", agent=agent.name)

    async def on_agent_end(self, context: AgentHookContext[Any], agent: Agent[Any], output: Any) -> None:
        print(f"DEBUG RunHooks.on_agent_end agent={agent.name!r}")
        journal.add("run_agent_end", agent=agent.name)

    async def on_handoff(
        self, context: RunContextWrapper[Any], from_agent: Agent[Any], to_agent: Agent[Any]
    ) -> None:
        print(f"DEBUG RunHooks.on_handoff from={from_agent.name!r} to={to_agent.name!r}")
        journal.add("run_handoff", from_agent=from_agent.name, to_agent=to_agent.name)

    async def on_tool_start(
        self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool
    ) -> None:
        n = getattr(tool, "name", type(tool).__name__)
        print(f"DEBUG RunHooks.on_tool_start agent={agent.name!r} tool={n!r}")

    async def on_tool_end(
        self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool, result: str
    ) -> None:
        n = getattr(tool, "name", type(tool).__name__)
        print(f"DEBUG RunHooks.on_tool_end agent={agent.name!r} tool={n!r}")


# ------------------- THREE AGENTS (writer defined first for forward refs) -------------------
writer_agent = Agent(
    name="Writer_Agent",
    instructions=(
        "You receive context after research. Call finalize_brief once with a concise markdown "
        "draft that summarizes the user's topic using the conversation so far. "
        "Then reply with a short confirmation; the tool returns the formatted brief."
    ),
    model=model,
    tools=[finalize_brief],
    hooks=AgentLevelHooks("WRITER"),
)

research_agent = Agent(
    name="Research_Agent",
    instructions=(
        "You handle factual gathering. Call fetch_topic_facts with the user's topic. "
        "Then hand off to Writer_Agent using the handoff tool: pass reason and key_points "
        "(key_points must contain the facts you collected). Do not skip the handoff."
    ),
    model=model,
    tools=[fetch_topic_facts],
    handoffs=[
        handoff(
            writer_agent,
            on_handoff=on_to_writer,
            input_type=ToWriterHandoff,
            tool_description_override=(
                "Transfer to Writer_Agent to produce the final brief. "
                "Provide reason and key_points (bullets/string of facts)."
            ),
        )
    ],
    hooks=AgentLevelHooks("RESEARCH"),
)

coordinator_agent = Agent(
    name="Coordinator_Agent",
    instructions=(
        "You are the front door. For any request about learning or explaining a technical topic, "
        "first call coordinator_checkpoint with a one-line note, then hand off to Research_Agent "
        "with a clear reason. Do not answer the topic yourself—delegate."
    ),
    model=model,
    tools=[coordinator_checkpoint],
    handoffs=[
        handoff(
            research_agent,
            on_handoff=on_to_research,
            input_type=ToResearchHandoff,
            tool_description_override=(
                "Transfer to Research_Agent to collect facts before writing. "
                "Always supply a short reason string."
            ),
        )
    ],
    hooks=AgentLevelHooks("COORDINATOR"),
)


def log_all_agent_configurations() -> None:
    for ag in (coordinator_agent, research_agent, writer_agent):
        log_agent_configuration(ag)


async def run_demo(user_message: str) -> str:
    print(f"\nDEBUG run_demo() start user_message={user_message!r}")

    result = await Runner.run(
        coordinator_agent,
        input=user_message,
        hooks=GlobalRunHooks(),
    )
    out = result.final_output
    print(f"DEBUG run_demo() final_output={str(out)!r}")
    return str(out)


async def main() -> None:
    demo_input = (
        "Explain asyncio to a junior developer: I want a short brief with facts and a clean summary."
    )
    log_all_agent_configurations()

    await run_demo(demo_input)

    out_path = _ROOT / "BasicExamples" / "three_agent_trace_journal.json"
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(journal.events, f, indent=2)
        print(f"\nWrote structured trace journal to: {out_path}")
    except OSError as e:
        print(f"\nCould not write journal file: {e}")


if __name__ == "__main__":
    asyncio.run(main())
