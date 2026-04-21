"""
List tools from Zapier MCP (FastMCP client). Env vars: see `mcp_config/zapier_mcp_config.py`.

  python mcp_config/zapier_mcp_list_tools.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(_REPO_ROOT / ".env")

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from mcp_config.zapier_mcp_config import env_truthy, get_zapier_api_key, get_zapier_server_url, REPO_ROOT


def _configure_logging() -> None:
    level = logging.DEBUG if env_truthy("MCP_DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def _tool_to_serializable(tool: object) -> dict:
    if hasattr(tool, "model_dump"):
        try:
            return tool.model_dump(mode="json")
        except TypeError:
            return tool.model_dump()
    out: dict = {}
    for key in ("name", "description", "title"):
        if hasattr(tool, key):
            val = getattr(tool, key)
            if val is not None:
                out[key] = val
    for key in ("inputSchema", "input_schema", "raw_input"):
        if hasattr(tool, key):
            out["inputSchema" if key == "input_schema" else key] = getattr(tool, key)
            break
    if not out and hasattr(tool, "__dict__"):
        out = {k: v for k, v in tool.__dict__.items() if not k.startswith("_")}
    return out


async def main() -> None:
    _configure_logging()
    log = logging.getLogger("zapier_mcp")

    api_key = get_zapier_api_key()
    server_url = get_zapier_server_url()

    log.debug("ZAPIER_MCP_URL=%r (len=%d)", server_url, len(server_url))
    log.debug("ZAPIER_MCP_API_KEY %s", f"set ({len(api_key)} chars)" if api_key else "MISSING")

    if not api_key:
        log.error("Set ZAPIER_MCP_API_KEY in %s or the environment.", REPO_ROOT / ".env")
        raise SystemExit(1)

    transport = StreamableHttpTransport(
        server_url,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    client = Client(transport=transport)

    log.info("Connecting to MCP server...")
    async with client:
        log.debug("client.is_connected() -> %s", client.is_connected())
        log.info("Fetching tools via client.list_tools()...")
        tools = await client.list_tools()
        log.debug("list_tools type=%s len=%d", type(tools), len(tools))

        names = [getattr(t, "name", str(t)) for t in tools]
        log.info("Tool count: %d", len(names))
        print(json.dumps({"tool_count": len(names), "tool_names": names}, indent=2))

        if env_truthy("MCP_DEBUG"):
            detailed = [_tool_to_serializable(t) for t in tools]
            log.debug("Full tool payloads:\n%s", json.dumps(detailed, indent=2, default=str))
            print("\n--- MCP_DEBUG: full tools ---")
            print(json.dumps(detailed, indent=2, default=str))

    log.info("Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
