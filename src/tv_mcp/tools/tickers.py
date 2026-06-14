"""Ticker-state tools (T1.1).

One tool per v2 ticker-state endpoint: ``get_ticker_state``, ``explain_ticker``,
``get_market_structure``, ``get_signals``, ``get_levels``. Each forwards to the client and
returns the v2 payload unchanged (it is already agent-shaped).
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ._common import normalize_ticker, with_tv


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="get_ticker_state",
        description=(
            "Get the canonical compact state snapshot for a ticker — the default starting "
            "point for analysis (price, gamma regime, IV rank, key positioning metrics). "
            "Optional `include` is a comma-separated list of add-ons (e.g. 'call_diag')."
        ),
    )
    async def get_ticker_state(ticker: str, include: str | None = None) -> dict[str, Any]:
        symbol = normalize_ticker(ticker)
        return await with_tv(
            lambda c: c.get_ticker_state(symbol, include=include), ticker=symbol
        )

    @mcp.tool(
        name="explain_ticker",
        description=(
            "Get a deterministic narrative interpretation of a ticker's current regime and "
            "positioning — a plain-language read of the state. Optional `view` selects an "
            "alternate explanation view when available."
        ),
    )
    async def explain_ticker(ticker: str, view: str | None = None) -> dict[str, Any]:
        symbol = normalize_ticker(ticker)
        return await with_tv(lambda c: c.explain_ticker(symbol, view=view), ticker=symbol)

    @mcp.tool(
        name="get_market_structure",
        description=(
            "Get the assembled market-structure interpretation for a ticker: headline signal, "
            "regime classification, expected behavior, key levels, and supporting metrics. "
            "Optional `include` adds sections (e.g. 'state', 'call_diag')."
        ),
    )
    async def get_market_structure(ticker: str, include: str | None = None) -> dict[str, Any]:
        symbol = normalize_ticker(ticker)
        return await with_tv(
            lambda c: c.get_market_structure(symbol, include=include), ticker=symbol
        )

    @mcp.tool(
        name="get_signals",
        description="Get the current signals for a ticker (active setup/positioning signals).",
    )
    async def get_signals(ticker: str) -> dict[str, Any]:
        symbol = normalize_ticker(ticker)
        return await with_tv(lambda c: c.get_signals(symbol), ticker=symbol)

    @mcp.tool(
        name="get_levels",
        description=(
            "Get key price levels for a ticker (gamma flip, walls, max pain, expected-move "
            "bounds). Optional `view` formats the output: 'json' (default), 'tradingview', "
            "or 'tos' (thinkorswim)."
        ),
    )
    async def get_levels(ticker: str, view: str | None = None) -> dict[str, Any]:
        symbol = normalize_ticker(ticker)
        return await with_tv(lambda c: c.get_levels(symbol, view=view), ticker=symbol)
