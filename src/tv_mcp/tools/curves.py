"""Curve & series tools (T1.2).

``get_series`` (metrics over a window), ``get_gamma_curve`` (per expiration, optionally
realtime), ``get_gamma_by_expiration`` (decomposition by expiration bucket),
``get_gex_by_strike`` (net GEX strike curve), and ``get_options_volume`` (volume by strike).
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ._common import error_envelope, normalize_ticker, with_tv


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="get_series",
        description=(
            "Get a historical daily time series for a ticker, for charting and regime "
            "context. `metrics` is a comma-separated list of metric keys (e.g. "
            "'price,iv_rank,gex_flip'); `window` is a lookback like '30d', '180d', or '2y'. "
            "Both are optional and fall back to the API defaults."
        ),
    )
    async def get_series(
        ticker: str, metrics: str | None = None, window: str | None = None
    ) -> dict[str, Any]:
        symbol = normalize_ticker(ticker)
        return await with_tv(
            lambda c: c.get_series(symbol, metrics=metrics, window=window), ticker=symbol
        )

    @mcp.tool(
        name="get_gamma_curve",
        description=(
            "Get the gamma strike curve (net gamma per strike) for a ticker. `exp` selects the "
            "expiration: 'combined' (default), 'nearest', 'first_weekly', 'first_monthly', or "
            "a 'YYYY-MM-DD' date. Set `realtime=true` for an intraday pull (requires trading "
            "hours when `exp` is a specific date)."
        ),
    )
    async def get_gamma_curve(
        ticker: str, exp: str | None = None, realtime: bool | None = None
    ) -> dict[str, Any]:
        symbol = normalize_ticker(ticker)
        return await with_tv(
            lambda c: c.get_gamma_curve(symbol, exp=exp, realtime=realtime), ticker=symbol
        )

    @mcp.tool(
        name="get_gamma_by_expiration",
        description=(
            "Get the strike-aligned gamma decomposition by expiration bucket for a ticker "
            "(combined, nearest, first_weekly, first_monthly, all_other_expiries)."
        ),
    )
    async def get_gamma_by_expiration(ticker: str) -> dict[str, Any]:
        symbol = normalize_ticker(ticker)
        return await with_tv(lambda c: c.get_gamma_by_expiration(symbol), ticker=symbol)

    @mcp.tool(
        name="get_gex_by_strike",
        description=(
            "Get the net GEX (gamma exposure) strike curve for a ticker, with call/put "
            "contributions — identifies key strikes and call-vs-put dominance. `exp` selects "
            "the expiration: 'combined' (default), 'nearest', or 'first_monthly'."
        ),
    )
    async def get_gex_by_strike(ticker: str, exp: str | None = None) -> dict[str, Any]:
        symbol = normalize_ticker(ticker)
        return await with_tv(lambda c: c.get_gex_by_strike(symbol, exp=exp), ticker=symbol)

    @mcp.tool(
        name="get_options_volume",
        description=(
            "Get real-time options volume aggregated by strike for a ticker and a specific "
            "expiration. `exp` (the expiration date, required) selects the contract month; set "
            "`include='iv'` to add implied-volatility columns."
        ),
    )
    async def get_options_volume(
        ticker: str, exp: str, include: str | None = None
    ) -> dict[str, Any]:
        if not exp or not exp.strip():
            return error_envelope(
                "invalid_input",
                "`exp` (expiration) is required for options volume.",
                "Pass an expiration date like '2026-06-19'.",
            )
        symbol = normalize_ticker(ticker)
        return await with_tv(
            lambda c: c.get_options_volume(symbol, exp=exp, include=include), ticker=symbol
        )
