import asyncio
import contextlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

from openai import BadRequestError
from pydantic import BaseModel, Field

from agents import (
    Agent,
    AgentHookContext,
    AgentHooks,
    RunContextWrapper,
    RunHooks,
    Runner,
    Tool,
    handoff,
    function_tool,
)

rootpath = Path(__file__).resolve().parent.parent
sys.path.append(str(rootpath))
from llm_model_config.llm_model_config import get_model_from_config

model = get_model_from_config()
LOG_PATH = Path(__file__).resolve().parent / "agnet_out_puttyep_debug.log"


class _Tee:
    """Write output to multiple streams (terminal + log file)."""

    def __init__(self, *streams: Any) -> None:
        self.streams = streams

    def write(self, data: str) -> int:
        for s in self.streams:
            s.write(data)
        return len(data)

    def flush(self) -> None:
        for s in self.streams:
            s.flush()


async def _slow_hook_delay() -> None:
    """Artificial delay to observe hook execution order clearly."""
    await asyncio.sleep(5)


def _section(title: str) -> None:
    print("\n==============================")
    print(title)
    print("==============================")


def _context_snapshot(label: str, context: RunContextWrapper[Any]) -> None:
    """Detailed debug print of what is inside RunContextWrapper/AgentHookContext."""
    ctx_obj = getattr(context, "context", None)
    usage = getattr(context, "usage", None)
    turn_input = getattr(context, "turn_input", None)
    tool_input = getattr(context, "tool_input", None)
    approvals = getattr(context, "_approvals", None)

    _section(f"runcontextwrapper :: {label}")
    print(f"DEBUG context_type={type(context).__name__!r} context_id={hex(id(context))}")
    print(f"DEBUG context.context type={type(ctx_obj).__name__!r} value={ctx_obj!r}")
    if usage is not None:
        print(
            "DEBUG context.usage "
            f"requests={getattr(usage, 'requests', None)!r} "
            f"input_tokens={getattr(usage, 'input_tokens', None)!r} "
            f"output_tokens={getattr(usage, 'output_tokens', None)!r} "
            f"total_tokens={getattr(usage, 'total_tokens', None)!r}"
        )
        req_entries = getattr(usage, "request_usage_entries", None)
        print(f"DEBUG context.usage.request_usage_entries_count={len(req_entries) if req_entries else 0}")
    else:
        print("DEBUG context.usage=None")
    if isinstance(turn_input, list):
        print(f"DEBUG context.turn_input_count={len(turn_input)}")
        preview_types = [type(i).__name__ for i in turn_input[:8]]
        print(f"DEBUG context.turn_input_types_preview={preview_types}")
    else:
        print(f"DEBUG context.turn_input={turn_input!r}")
    print(f"DEBUG context.tool_input={tool_input!r}")
    if isinstance(approvals, dict):
        print(f"DEBUG context._approvals_keys={list(approvals.keys())}")
    else:
        print(f"DEBUG context._approvals={approvals!r}")
    # Explicit schema-fill view (what attributes are currently known in run context)
    if isinstance(ctx_obj, dict):
        payload = ctx_obj.get("handoff_payload") if "handoff_payload" in ctx_obj else None
        if isinstance(payload, dict):
            schema_keys = ["company_name", "stock_price", "recent_news_summary", "risk_level"]
            present = {k: payload.get(k) for k in schema_keys if k in payload}
            missing = [k for k in schema_keys if k not in payload or payload.get(k) in (None, "", [])]
            print(
                f"DEBUG schema_progress source='context[\"handoff_payload\"]' "
                f"present_keys={list(present.keys())} missing_keys={missing}"
            )
            print(f"DEBUG schema_progress values={present!r}")
        else:
            print("DEBUG schema_progress source='context' no handoff_payload yet")
    else:
        print("DEBUG schema_progress source='context' unavailable (non-dict context)")


def _agent_debug_info(agent: Agent[Any]) -> str:
    tool_names = [getattr(t, "name", type(t).__name__) for t in (agent.tools or [])]
    return (
        f"name={agent.name!r}, "
        f"model={getattr(agent, 'model', None)!r}, "
        f"output_type={getattr(agent, 'output_type', None)!r}, "
        f"tools={tool_names}, "
        f"handoff_count={len(agent.handoffs or [])}"
    )


async def debug_runner_run(
    starting_agent: Agent[Any],
    run_input: Any,
    *,
    hooks: RunHooks | None = None,
    context: Any = None,
) -> Any:
    _section("runner.run :: START")
    print("DEBUG BEFORE Runner.run CALL")
    print(f"DEBUG start_agent_info: {_agent_debug_info(starting_agent)}")
    print(f"DEBUG run_input_preview: {str(run_input)[:240]!r}")
    print(f"DEBUG hooks_object: {type(hooks).__name__ if hooks else None}")
    print(f"DEBUG context_before_run: {context!r}")
    print("DEBUG I am inside wrapper before calling Runner.run(...)")
    result = await Runner.run(starting_agent, run_input, hooks=hooks, context=context)
    _section("runner.run :: END")
    print("DEBUG Runner.run RETURNED")
    print(f"DEBUG final_output_type: {type(result.final_output).__name__!r}")
    print(f"DEBUG final_output_preview: {str(result.final_output)[:240]!r}")
    return result


class AgentLevelHooks(AgentHooks):
    """Per-agent lifecycle hooks (Agent(..., hooks=AgentLevelHooks(...)))."""

    def __init__(self, label: str) -> None:
        self.label = label
        self._t0: float | None = None
        self.instance_id = hex(id(self))
        print(
            f"DEBUG HOOK-WIRE AgentLevelHooks created "
            f"label={self.label!r} instance_id={self.instance_id}"
        )

    async def on_start(self, context: AgentHookContext[Any], agent: Agent[Any]) -> None:
        await _slow_hook_delay()
        self._t0 = time.time()
        _section(f"agentlevelhooks :: {agent.name} :: on_start")
        print(
            f"DEBUG AgentHooks.on_start label={self.label!r} "
            f"hook_instance={self.instance_id} agent={agent.name!r}"
        )
        if self.label == "research" and agent.name == "Finance Researcher":
            print("DEBUG HOOK-ROUTE AgentLevelHooks('research') is active on Finance Researcher")
        elif self.label == "formatter" and agent.name == "Finance Report Formatter":
            print("DEBUG HOOK-ROUTE AgentLevelHooks('formatter') is active on Finance Report Formatter")
        else:
            print(
                f"DEBUG HOOK-ROUTE label={self.label!r} is active on agent={agent.name!r} "
                "(custom mapping)"
            )
        _context_snapshot("AgentHooks.on_start", context)

    async def on_end(self, context: AgentHookContext[Any], agent: Agent[Any], output: Any) -> None:
        await _slow_hook_delay()
        elapsed = time.time() - self._t0 if self._t0 else 0.0
        _section(f"agentlevelhooks :: {agent.name} :: on_end")
        usage = getattr(context, "usage", None)
        tok = f" total_tokens={usage.total_tokens}" if usage else ""
        print(f"DEBUG AgentHooks.on_end label={self.label!r} agent={agent.name!r} elapsed_s={elapsed:.3f}{tok}")
        # Show which schema attributes are present in this agent's output object/text.
        if isinstance(output, CompetitorReport):
            print(
                "DEBUG schema_fill_by_agent "
                f"agent={agent.name!r} output_type='CompetitorReport' "
                f"fields={{'company_name': {output.company_name!r}, "
                f"'stock_price': {output.stock_price!r}, "
                f"'recent_news_summary': {output.recent_news_summary[:80]!r}, "
                f"'risk_level': {output.risk_level!r}}}"
            )
        else:
            out_text = str(output)
            print(
                "DEBUG schema_fill_by_agent "
                f"agent={agent.name!r} output_type={type(output).__name__!r} "
                f"output_preview={out_text[:200]!r}"
            )
        _context_snapshot("AgentHooks.on_end", context)

    async def on_handoff(
        self, context: RunContextWrapper[Any], agent: Agent[Any], source: Agent[Any]
    ) -> None:
        await _slow_hook_delay()
        _section(f"agentlevelhooks :: handoff :: {source.name} -> {agent.name}")
        print(f"DEBUG AgentHooks.on_handoff receiving={agent.name!r} from={source.name!r}")
        _context_snapshot("AgentHooks.on_handoff", context)

    async def on_tool_start(
        self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool
    ) -> None:
        await _slow_hook_delay()
        print(f"DEBUG AgentHooks.on_tool_start agent={agent.name!r} tool={getattr(tool, 'name', type(tool).__name__)!r}")
        _context_snapshot("AgentHooks.on_tool_start", context)

    async def on_tool_end(
        self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool, result: Any
    ) -> None:
        await _slow_hook_delay()
        result_text = str(result)
        rp = result_text[:120] + ("..." if len(result_text) > 120 else "")
        print(f"DEBUG AgentHooks.on_tool_end agent={agent.name!r} tool={getattr(tool, 'name', type(tool).__name__)!r} result={rp!r}")
        _context_snapshot("AgentHooks.on_tool_end", context)

    async def on_llm_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        system_prompt: Optional[str],
        input_items: list[Any],
    ) -> None:
        await _slow_hook_delay()
        item_types = [type(i).__name__ for i in input_items[:8]]
        print(f"DEBUG AgentHooks.on_llm_start agent={agent.name!r} items={len(input_items)}")
        print(
            "DEBUG AgentHooks.on_llm_start what is sent to LLM: "
            f"system_prompt_preview={(system_prompt or '')[:140]!r}, input_item_types={item_types}"
        )
        print(
            "DEBUG AgentHooks.on_llm_start where saved in context wrapper: "
            f"context.turn_input_count={len(getattr(context, 'turn_input', []) or [])}, "
            f"context.tool_input={getattr(context, 'tool_input', None)!r}"
        )
        _context_snapshot("AgentHooks.on_llm_start", context)

    async def on_llm_end(
        self, context: RunContextWrapper[Any], agent: Agent[Any], response: Any
    ) -> None:
        await _slow_hook_delay()
        print(f"DEBUG AgentHooks.on_llm_end agent={agent.name!r} response={type(response).__name__!r}")
        _context_snapshot("AgentHooks.on_llm_end", context)


class GlobalRunHooks(RunHooks):
    """Global/session lifecycle hooks (Runner.run(..., hooks=GlobalRunHooks()))."""

    async def on_agent_start(self, context: AgentHookContext[Any], agent: Agent[Any]) -> None:
        await _slow_hook_delay()
        _section(f"globalrunhooks :: {agent.name} :: on_agent_start")
        print(
            f"DEBUG RunHooks.on_agent_start agent={agent.name!r} "
            "(global hook from Runner.run(..., hooks=GlobalRunHooks()))"
        )
        _context_snapshot("RunHooks.on_agent_start", context)

    async def on_agent_end(self, context: AgentHookContext[Any], agent: Agent[Any], output: Any) -> None:
        await _slow_hook_delay()
        _section(f"globalrunhooks :: {agent.name} :: on_agent_end")
        print(f"DEBUG RunHooks.on_agent_end agent={agent.name!r}")
        _context_snapshot("RunHooks.on_agent_end", context)

    async def on_handoff(
        self, context: RunContextWrapper[Any], from_agent: Agent[Any], to_agent: Agent[Any]
    ) -> None:
        await _slow_hook_delay()
        print(f"DEBUG RunHooks.on_handoff from={from_agent.name!r} to={to_agent.name!r}")
        _context_snapshot("RunHooks.on_handoff", context)

    async def on_tool_start(
        self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool
    ) -> None:
        await _slow_hook_delay()
        print(f"DEBUG RunHooks.on_tool_start agent={agent.name!r} tool={getattr(tool, 'name', type(tool).__name__)!r}")
        _context_snapshot("RunHooks.on_tool_start", context)

    async def on_tool_end(
        self, context: RunContextWrapper[Any], agent: Agent[Any], tool: Tool, result: Any
    ) -> None:
        await _slow_hook_delay()
        result_text = str(result)
        rp = result_text[:120] + ("..." if len(result_text) > 120 else "")
        print(f"DEBUG RunHooks.on_tool_end agent={agent.name!r} tool={getattr(tool, 'name', type(tool).__name__)!r} result={rp!r}")
        _context_snapshot("RunHooks.on_tool_end", context)

    async def on_llm_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        system_prompt: Optional[str],
        input_items: list[Any],
    ) -> None:
        await _slow_hook_delay()
        item_types = [type(i).__name__ for i in input_items[:8]]
        print(f"DEBUG RunHooks.on_llm_start agent={agent.name!r} items={len(input_items)}")
        print(
            "DEBUG RunHooks.on_llm_start payload_summary: "
            f"system_prompt_preview={(system_prompt or '')[:140]!r}, input_item_types={item_types}"
        )
        _context_snapshot("RunHooks.on_llm_start", context)

    async def on_llm_end(
        self, context: RunContextWrapper[Any], agent: Agent[Any], response: Any
    ) -> None:
        await _slow_hook_delay()
        print(f"DEBUG RunHooks.on_llm_end agent={agent.name!r} response={type(response).__name__!r}")
        _context_snapshot("RunHooks.on_llm_end", context)

# 1. Define the Final Output Schema
class CompetitorReport(BaseModel):
    company_name: str
    stock_price: float
    recent_news_summary: str
    risk_level: str = Field(description="Low, Medium, or High based on news")


class ToFormatterHandoff(BaseModel):
    company_name: str
    stock_price: float
    recent_news_summary: str
    risk_level: str = Field(description="Low, Medium, or High")

# 2. Define the Tools
def _stock_price_value(ticker: str) -> float:
    """Internal callable helper used by tool + fallback."""
    # Logic to call a finance API
    return 150.25


def _recent_news_value(company: str) -> list[str]:
    """Internal callable helper used by tool + fallback."""
    return ["Launched new AI chip", "Quarterly earnings beat expectations", "Expansion into Europe"]


def _company_details_value(company: str) -> str:
    """Internal callable helper used by tool + fallback."""
    return "Tech giant focused on semiconductors and AI."


@function_tool
def get_stock_price(ticker: str) -> float:
    """Fetches real-time stock price for a ticker."""
    return _stock_price_value(ticker)

@function_tool
def search_recent_news(company: str) -> list[str]:
    """Searches for the 3 latest news headlines for a company."""
    return _recent_news_value(company)

@function_tool
def get_company_details(company: str) -> str:
    """Gets general company background."""
    return _company_details_value(company)


def _normalize_report_dict(raw: dict) -> dict:
    """Coerce model JSON into CompetitorReport-compatible types."""
    data = dict(raw)

    stock = data.get("stock_price")
    if isinstance(stock, str):
        # Accept values like "USD 150.25" or "$150.25"
        m = re.search(r"[-+]?\d*\.?\d+", stock)
        if m:
            data["stock_price"] = float(m.group(0))

    news = data.get("recent_news_summary")
    if isinstance(news, list):
        data["recent_news_summary"] = "; ".join(str(x) for x in news)

    risk = data.get("risk_level")
    if isinstance(risk, str):
        normalized = risk.strip().capitalize()
        if normalized in {"Low", "Medium", "High"}:
            data["risk_level"] = normalized

    return data

formatter_agent = Agent(
    name="Finance Report Formatter",
    instructions="""
    You receive transfer payload from Finance Researcher.
    Return final output as CompetitorReport with:
    - company_name
    - stock_price (number)
    - recent_news_summary (string)
    - risk_level (Low, Medium, High)
    """,
    output_type=CompetitorReport,
    model=model,
    hooks=AgentLevelHooks("formatter"),
)

# Fallback formatter (no output_type) for providers that fail strict JSON validation.
formatter_fallback_agent = Agent(
    name="Finance Report Formatter Fallback",
    instructions="""
    Return ONLY valid JSON (no markdown/prose) with keys:
    company_name, stock_price, recent_news_summary, risk_level
    risk_level must be one of: Low, Medium, High.
    stock_price must be a plain number.
    recent_news_summary must be one string.
    """,
    model=model,
    hooks=AgentLevelHooks("formatter_fallback"),
)


async def on_handoff_to_formatter(
    ctx: RunContextWrapper[Any], data: ToFormatterHandoff
) -> None:
    # Keep a copy in run context for debugging/inspection if needed.
    if isinstance(ctx.context, dict):
        ctx.context["handoff_payload"] = data.model_dump()
        ctx.context["schema_filled_by"] = "Finance Researcher"
        ctx.context["schema_fill_stage"] = "handoff_to_formatter"
    print(f"DEBUG handoff callback → formatter payload={data.model_dump()!r}")
    print(
        "DEBUG schema_fill_event "
        "agent='Finance Researcher' stage='handoff' "
        f"filled_fields={list(data.model_dump().keys())}"
    )


# 3. Build agents:
# - Research agent uses tools and transfers structured payload to formatter.
# - Formatter has output_type at agent level and ends the run.
research_agent = Agent(
    name="Finance Researcher",
    instructions="""
    You are a financial analyst.
    1. Use tools to get company details, stock price, and latest news.
    2. Determine risk_level (Low, Medium, High) from the news.
    3. Call transfer_to_finance_report_formatter with:
       company_name, stock_price, recent_news_summary, risk_level.
       recent_news_summary must be a single string summary.
    Do not give final answer yourself; always transfer.
    """,
    tools=[get_stock_price, search_recent_news, get_company_details],
    handoffs=[
        handoff(
            formatter_agent,
            input_type=ToFormatterHandoff,
            on_handoff=on_handoff_to_formatter,
        )
    ],
    model=model,
    hooks=AgentLevelHooks("research"),
)

async def main():
    run_hooks = GlobalRunHooks()
    print("\nDEBUG WIRING-SUMMARY START")
    print(
        f"DEBUG WIRING research_agent.hooks -> type={type(research_agent.hooks).__name__} "
        f"label={getattr(research_agent.hooks, 'label', None)!r} "
        f"instance_id={getattr(research_agent.hooks, 'instance_id', None)!r}"
    )
    print(
        f"DEBUG WIRING formatter_agent.hooks -> type={type(formatter_agent.hooks).__name__} "
        f"label={getattr(formatter_agent.hooks, 'label', None)!r} "
        f"instance_id={getattr(formatter_agent.hooks, 'instance_id', None)!r}"
    )
    print(
        "DEBUG WIRING NOTE Agent-level hook attach points:\n"
        "  - research_agent uses hooks=AgentLevelHooks('research')\n"
        "  - formatter_agent uses hooks=AgentLevelHooks('formatter')"
    )
    print(
        f"DEBUG WIRING NOTE Global run hook instance={hex(id(run_hooks))} "
        "passed to Runner.run(..., hooks=run_hooks)"
    )
    print("DEBUG WIRING-SUMMARY END\n")
    # Single end-to-end run: research (tools) -> handoff -> formatter (output_type)
    try:
        result = await debug_runner_run(
            research_agent,
            "Analyze NVIDIA for me.",
            hooks=run_hooks,
            context={},
        )
        report = result.final_output
        if not isinstance(report, CompetitorReport):
            report = CompetitorReport.model_validate(_normalize_report_dict(dict(report)))
    except BadRequestError as e:
        # Keep output_type as primary path; fallback only for provider JSON validation failures.
        if "json_validate_failed" not in str(e):
            raise
        print("DEBUG FALLBACK triggered: provider failed strict output_type JSON validation")
        print(f"DEBUG FALLBACK cause: {e}")
        # Re-run with tools only, then format as plain JSON and validate locally.
        research_only_agent = Agent(
            name="Finance Researcher Fallback",
            instructions="""
            Use tools to gather company details, stock price, and recent news.
            Return a concise plain-text analysis with values for:
            company_name, stock_price, recent_news_summary, risk_level.
            """,
            tools=[get_stock_price, search_recent_news, get_company_details],
            model=model,
            hooks=AgentLevelHooks("research_fallback"),
        )
        research_result = await debug_runner_run(
            research_only_agent,
            "Analyze NVIDIA for me.",
            hooks=run_hooks,
        )
        format_prompt = (
            "Convert this analysis into JSON only with keys "
            "company_name, stock_price, recent_news_summary, risk_level:\n\n"
            f"{research_result.final_output}"
        )
        formatted_result = await debug_runner_run(
            formatter_fallback_agent,
            format_prompt,
            hooks=run_hooks,
        )
        parsed = json.loads(str(formatted_result.final_output))
        parsed = _normalize_report_dict(parsed)
        report = CompetitorReport.model_validate(parsed)
    print(f"Company: {report.company_name}")
    print(f"Stock: {report.stock_price}")
    print(f"Risk: {report.risk_level}")

if __name__ == "__main__":
    with open(LOG_PATH, "w", encoding="utf-8") as log_file:
        tee_out = _Tee(sys.__stdout__, log_file)
        tee_err = _Tee(sys.__stderr__, log_file)
        with contextlib.redirect_stdout(tee_out), contextlib.redirect_stderr(tee_err):
            print(f"DEBUG LOG FILE: {LOG_PATH}")
            asyncio.run(main())