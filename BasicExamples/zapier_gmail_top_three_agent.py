# ============================== DEVELOPER INFO ======================================
# Name: Onteru Yallaiah
# OpenAI Agents SDK + Zapier MCP (streamable HTTP) — recent Gmail via gmail_find_email.
# Env: see mcp_config/zapier_mcp_config.py (Zapier + Gmail + optional timeouts).
# *************************************************************************************
import asyncio
import inspect
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp, create_static_tool_filter

root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))
load_dotenv(root_path / ".env")

from llm_model_config.llm_model_config import ModelSingleton
from mcp_config.zapier_mcp_config import (
    gmail_agent_max_turns,
    gmail_dump_raw_mcp_default_on,
    get_gmail_email_count,
    get_gmail_search_query,
    get_zapier_api_key,
    zapier_mcp_client_session_timeout,
    zapier_streamable_http_params,
)

model = ModelSingleton.get_instance()
if model is None:
    raise RuntimeError("Model failed to load; set GROQ_API_KEY and model_name in .env")

print("✅ Model loaded from config")

GMAIL_READER_INSTRUCTIONS = """
You read Gmail through Zapier MCP only.

Goal: Show the user's **N most recent** matching emails with **full content**, not one-line summaries.

Rules:
- Use **only** `gmail_find_email`. You may call it twice only if the first call returns too few rows or clearly truncated bodies and a narrower query might help.
- The user message will give an **exact Gmail search query** string — pass it to the tool as required by the tool schema (often a `query` field, sometimes plus Zapier `instructions`).
- If the tool exposes a **limit / max results** (or similar), set it **high** (e.g. 15–20), then sort by date and keep only the **N newest** the user asked for.
- For **each** of those N emails, include every useful field the tool returns, especially:
  **Subject, From, To, Cc, Date,** and the **entire plain-text body**. If there is no plain text but there is HTML, paste the **full HTML** inside a fenced ```html block. If only a short snippet exists, paste the snippet and state that Zapier did not return a full body.
- **Do not** replace the body with your own summary. You may add a one-line header per email, but the body must be the tool output (or clearly marked as missing).
- Never call send, draft, delete, archive, label, or attachment tools.
- If fewer than N messages match, list all matches and give the count.
""".strip()


def log_info(message: str) -> None:
    frame = inspect.currentframe()
    if frame is None or frame.f_back is None:
        line_no = "?"
    else:
        line_no = frame.f_back.f_lineno
    yellow, bold, reset = "\033[93m", "\033[1m", "\033[0m"
    print(f"{bold}{yellow}[LINE {line_no}]{reset} INFO: {message}")


def _build_user_prompt() -> str:
    query = get_gmail_search_query()
    n = get_gmail_email_count()
    return (
        f"Use this Gmail search query verbatim when calling gmail_find_email: {query!r}\n\n"
        f"Return the {n} newest matching emails (newest first).\n"
        "Include full bodies as returned by the tool (see system instructions). "
        "If the tool schema has a limit parameter, use at least 15 so you can pick the "
        f"correct top {n} by date."
    )


def _dump_gmail_mcp_outputs(result: object) -> None:
    new_items = getattr(result, "new_items", None)
    if not new_items:
        return
    printed = 0
    for item in new_items:
        if getattr(item, "type", None) != "tool_call_output_item":
            continue
        out = getattr(item, "output", None)
        printed += 1
        print(f"\n--- Raw MCP tool output #{printed} ---")
        if isinstance(out, str):
            print(out)
        else:
            try:
                print(json.dumps(out, indent=2, default=str))
            except TypeError:
                print(repr(out))
    if printed == 0:
        log_info("No tool_call_output_item entries in run (check model/tool errors).")


async def main() -> None:
    log_info("Start: Zapier Gmail reader.")

    api_key = get_zapier_api_key()
    if not api_key:
        log_info("Stop: set ZAPIER_MCP_API_KEY in project .env")
        raise SystemExit(1)

    log_info("Zapier MCP configured.")

    tool_filter = create_static_tool_filter(allowed_tool_names=["gmail_find_email"])
    http_params = zapier_streamable_http_params(api_key=api_key)

    async with MCPServerStreamableHttp(
        params=http_params,
        name="zapier_gmail",
        cache_tools_list=True,
        client_session_timeout_seconds=zapier_mcp_client_session_timeout(),
        tool_filter=tool_filter,
        require_approval="never",
    ) as zapier_mcp:
        log_info("MCP session ready (gmail_find_email only).")

        agent = Agent(
            name="GmailTopThreeReader",
            instructions=GMAIL_READER_INSTRUCTIONS,
            model=model,
            mcp_servers=[zapier_mcp],
        )

        log_info("Runner: model + MCP…")
        result = await Runner.run(
            agent,
            input=_build_user_prompt(),
            max_turns=gmail_agent_max_turns(),
        )
        log_info("Runner: done.")

    if gmail_dump_raw_mcp_default_on():
        _dump_gmail_mcp_outputs(result)

    print("\n--- Final answer (model) ---\n")
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
