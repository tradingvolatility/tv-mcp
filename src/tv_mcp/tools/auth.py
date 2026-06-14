"""Auth status tool: ``get_auth_status``.

Reports whether credentials resolve and in which mode (keyed vs. demo), so an agent can tell
the user how to add a key before a non-demo call fails. Never returns or logs the API key.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ..auth import resolve_request_credential
from ..settings import DEMO_TICKERS, get_settings


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="get_auth_status",
        description=(
            "Check how the Trading Volatility MCP is authenticated for this session. Returns "
            "mode='keyed' when an API key is present (full access), or mode='demo' when no key "
            "is set (only the demo tickers are available). Does not reveal the key."
        ),
    )
    async def get_auth_status() -> dict[str, Any]:
        credential = resolve_request_credential()
        if credential.is_demo:
            if get_settings().tv_require_key:
                return {
                    "mode": "key_required",
                    "base_url": credential.base_url,
                    "message": (
                        "This server requires an API key; demo mode is disabled. Send an "
                        "Authorization: Bearer <key> header."
                    ),
                }
            return {
                "mode": "demo",
                "base_url": credential.base_url,
                "demo_tickers": sorted(DEMO_TICKERS),
                "message": (
                    "No API key set. Only the demo tickers are available. Add your key to "
                    "config.json (local) or send an Authorization: Bearer <key> header (remote)."
                ),
            }
        return {
            "mode": "keyed",
            "base_url": credential.base_url,
            "message": "API key present. Full access subject to your subscription.",
        }
