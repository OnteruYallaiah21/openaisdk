"""
Minimal run: 2 agents, 2 tools, short DEBUG observations.

Flow (expected): Router calls ``trace_step`` → hands off to Worker → Worker calls ``fetch_stub`` → final text.

    python BasicExamples/two_agent_two_tools_demo.py

Uses ``get_model_from_config()`` (Groq via ``GROQ_API_KEY`` + ``model_name`` in ``.env``).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from llm_model_config.llm_model_config import get_model_from_config

model = get_model_from_config()
print(f"DEBUG get_model_from_config model_id={getattr(model, 'model', model)!r}")

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


class ToWorkerHandoff(BaseModel):
    reason: str = Field(description="Why handing off to Worker")


async def on_handoff_to_worker(ctx: RunContextWrapper[Any], data: ToWorkerHandoff) -> None:
    print(f"DEBUG handoff callback → Worker reason={data.reason!r}")


# --- exactly 2 tools ---
@function_tool
def trace_step(where: str) -> str:
    print(f"DEBUG tool trace_step where={where!r}")
    return f"step_ok:{where}"


@function_tool
def fetch_stub(query: str) -> str:
    print(f"DEBUG tool fetch_stub query={query!r}")
    return f"stub facts for {query!r} (demo)"


class AgentLevelHooks(AgentHooks):
    """All ``AgentHooks`` callbacks (per-agent → ``Agent(..., hooks=...)``)."""

    async def on_start(self, context: AgentHookContext[Any], agent: Agent[Any]) -> None:
        print(f"DEBUG AgentHooks.on_start agent={agent.name!r}")

    async def on_end(self, context: AgentHookContext[Any], agent: Agent[Any], output: Any) -> None:
        u = getattr(context, "usage", None)
        tok = f" usage_total={u.total_tokens}" if u else ""
        print(f"DEBUG AgentHooks.on_end agent={agent.name!r}{tok}")

    async def on_handoff(
        self, context: RunContextWrapper[Any], agent: Agent[Any], source: Agent[Any]
    ) -> None:
        print(f"DEBUG AgentHooks.on_handoff receiving_agent={agent.name!r} from={source.name!r}")

    async def on_tool_start(
        self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool
    ) -> None:
        n = getattr(tool, "name", type(tool).__name__)
        print(f"DEBUG AgentHooks.on_tool_start agent={agent.name!r} tool={n!r}")

    async def on_tool_end(
        self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool, result: str
    ) -> None:
        n = getattr(tool, "name", type(tool).__name__)
        rp = result[:120] + ("..." if len(result) > 120 else "")
        print(f"DEBUG AgentHooks.on_tool_end agent={agent.name!r} tool={n!r} result_preview={rp!r}")

    async def on_llm_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        system_prompt: Optional[str],
        input_items: list[Any],
    ) -> None:
        sp = (system_prompt or "")[:80]
        print(
            f"DEBUG AgentHooks.on_llm_start agent={agent.name!r} items={len(input_items)} "
            f"system_prompt_preview={sp!r}"
        )

    async def on_llm_end(
        self, context: RunContextWrapper[Any], agent: Agent[Any], response: Any
    ) -> None:
        print(f"DEBUG AgentHooks.on_llm_end agent={agent.name!r} response_type={type(response).__name__!r}")


class GlobalRunHooks(RunHooks):
    """All ``RunHooks`` callbacks (session / multi-agent → ``Runner.run(..., hooks=...)``)."""

    async def on_agent_start(self, context: AgentHookContext[Any], agent: Agent[Any]) -> None:
        print(f"DEBUG RunHooks.on_agent_start active_agent={agent.name!r}")

    async def on_agent_end(self, context: AgentHookContext[Any], agent: Agent[Any], output: Any) -> None:
        preview = str(output)[:120] + ("..." if len(str(output)) > 120 else "")
        print(f"DEBUG RunHooks.on_agent_end agent={agent.name!r} output_preview={preview!r}")

    async def on_handoff(
        self, context: RunContextWrapper[Any], from_agent: Agent[Any], to_agent: Agent[Any]
    ) -> None:
        print(f"DEBUG RunHooks.on_handoff from={from_agent.name!r} to={to_agent.name!r}")

    async def on_tool_start(
        self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool
    ) -> None:
        n = getattr(tool, "name", type(tool).__name__)
        print(f"DEBUG RunHooks.on_tool_start agent={agent.name!r} tool={n!r}")

    async def on_tool_end(
        self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool, result: str
    ) -> None:
        n = getattr(tool, "name", type(tool).__name__)
        rp = result[:120] + ("..." if len(result) > 120 else "")
        print(f"DEBUG RunHooks.on_tool_end agent={agent.name!r} tool={n!r} result_preview={rp!r}")

    async def on_llm_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        system_prompt: Optional[str],
        input_items: list[Any],
    ) -> None:
        sp = (system_prompt or "")[:80]
        print(
            f"DEBUG RunHooks.on_llm_start agent={agent.name!r} items={len(input_items)} "
            f"system_prompt_preview={sp!r}"
        )

    async def on_llm_end(
        self, context: RunContextWrapper[Any], agent: Agent[Any], response: Any
    ) -> None:
        print(f"DEBUG RunHooks.on_llm_end agent={agent.name!r} response_type={type(response).__name__!r}")


# --- exactly 2 agents (define worker first for forward ref) ---
worker_agent = Agent(
    name="Worker",
    instructions="Call fetch_stub once with the user's topic (short string). Then answer in one sentence.",
    model=model,
    tools=[fetch_stub],
    hooks=AgentLevelHooks(),
)

router_agent = Agent(
    name="Router",
    instructions=(
        "First call trace_step with where='router'. Then hand off to Worker so it can fetch_stub "
        "for the user's question. Do not answer the topic yourself. Fill ``reason`` on transfer."
    ),
    model=model,
    tools=[trace_step],
    handoffs=[handoff(worker_agent, input_type=ToWorkerHandoff, on_handoff=on_handoff_to_worker)],
    hooks=AgentLevelHooks(),
)


async def main() -> None:
    print("Observations: 2 agents (Router, Worker), 2 tools (trace_step, fetch_stub).\n")

    user = "What is Redis used for?"
    print(f"DEBUG main input={user!r}\n")
    result = await Runner.run(router_agent, input=user, hooks=GlobalRunHooks())
    print(f"\nDEBUG main final_output={result.final_output!r}")


if __name__ == "__main__":
    asyncio.run(main())
