"""
Shared Zapier MCP settings (process env or repo-root `.env`).

Call `load_dotenv(REPO_ROOT / ".env")` (or equivalent) before reading values.

Environment variables
---------------------
Zapier (HTTP MCP):
  ZAPIER_MCP_API_KEY          — required for authenticated calls
  ZAPIER_MCP_URL              — optional; default Zapier connect URL
  ZAPIER_MCP_HTTP_TIMEOUT     — optional; default 60 (seconds)
  ZAPIER_MCP_SSE_READ_TIMEOUT — optional; default 300 (seconds)
  ZAPIER_MCP_CLIENT_SESSION_TIMEOUT — optional; Agents SDK session read timeout; default 120

Gmail reader example (BasicExamples/zapier_gmail_top_three_agent.py):
  GMAIL_SEARCH_QUERY   — Gmail search string; default "in:inbox newer_than:30d"
  GMAIL_EMAIL_COUNT    — default 3
  GMAIL_DUMP_RAW_MCP   — 1/true prints raw MCP tool output; default on
  GMAIL_AGENT_MAX_TURNS — default 15

Diagnostics (mcp_config/zapier_mcp_list_tools.py):
  MCP_DEBUG — verbose logging when truthy
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

ZAPIER_MCP_DEFAULT_URL = "https://mcp.zapier.com/api/v1/connect"
DEFAULT_GMAIL_QUERY = "in:inbox newer_than:30d"


def env_truthy(name: str, default: bool = False) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if v == "":
        return default
    return v in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def get_zapier_api_key() -> str:
    return (os.getenv("ZAPIER_MCP_API_KEY") or "").strip()


def get_zapier_server_url() -> str:
    return (os.getenv("ZAPIER_MCP_URL") or ZAPIER_MCP_DEFAULT_URL).strip()


def zapier_streamable_http_params(
    api_key: str | None = None,
    server_url: str | None = None,
) -> dict:
    """Params dict for `MCPServerStreamableHttp` / similar HTTP MCP clients."""
    key = (api_key or get_zapier_api_key()).strip()
    url = (server_url or get_zapier_server_url()).strip()
    return {
        "url": url,
        "headers": {"Authorization": f"Bearer {key}"},
        "timeout": _env_float("ZAPIER_MCP_HTTP_TIMEOUT", 60.0),
        "sse_read_timeout": _env_float("ZAPIER_MCP_SSE_READ_TIMEOUT", 300.0),
    }


def zapier_mcp_client_session_timeout() -> float:
    return _env_float("ZAPIER_MCP_CLIENT_SESSION_TIMEOUT", 120.0)


def get_gmail_search_query() -> str:
    return (os.getenv("GMAIL_SEARCH_QUERY") or DEFAULT_GMAIL_QUERY).strip()


def get_gmail_email_count() -> int:
    try:
        return max(1, int(os.getenv("GMAIL_EMAIL_COUNT", "3")))
    except ValueError:
        return 3


def gmail_dump_raw_mcp_default_on() -> bool:
    return env_truthy("GMAIL_DUMP_RAW_MCP", default=True)


def gmail_agent_max_turns() -> int:
    try:
        return max(1, int(os.getenv("GMAIL_AGENT_MAX_TURNS", "15")))
    except ValueError:
        return 15
