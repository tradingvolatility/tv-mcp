"""Discovery, ranking, and capability tools (T1.3, T1.4).

``rank_top_setups`` and ``run_screener`` expose the cross-ticker opportunity ranking (the
screener applies a named thesis preset over the same ranking). ``rank_income_setups`` ranks
covered-call / cash-secured-put income candidates across tickers. ``get_trade_setup`` returns
the compact agent-oriented trade setup for one ticker. ``list_capabilities`` returns the v2
``/llm-spec`` manifest so an agent can self-orient and iteratively discover what's available.
"""

from __future__ import annotations

import re
from typing import Any

from mcp.server.fastmcp import FastMCP

from ._common import error_envelope, normalize_ticker, with_tv

# Screener names are snake_case identifiers. Restricting the charset keeps caller input out of
# the upstream URL path (no '/', '..', or query smuggling), the same guarantee as for tickers.
_SCREENER_NAME_RE = re.compile(r"^[a-z0-9_]{1,64}$")


def _ranking_params(
    *,
    limit: int | None,
    min_score: float | None,
    regime: str | None,
    recommended_direction: str | None,
    trade_bias: str | None,
    trend_state: str | None,
    momentum_state: str | None,
    realized_vol_state: str | None,
    iv_rank_min: float | None,
    iv_rank_max: float | None,
    price_min: float | None,
    price_max: float | None,
) -> dict[str, Any]:
    """Assemble the shared top-setups/screener query params, dropping unset values."""
    params: dict[str, Any] = {
        "limit": limit,
        "min_score": min_score,
        "regime": regime,
        "recommended_direction": recommended_direction,
        "trade_bias": trade_bias,
        "trend_state": trend_state,
        "momentum_state": momentum_state,
        "realized_vol_state": realized_vol_state,
        "iv_rank_min": iv_rank_min,
        "iv_rank_max": iv_rank_max,
        "price_min": price_min,
        "price_max": price_max,
    }
    return {k: v for k, v in params.items() if v is not None}


def _validate_ranking_params(
    *,
    limit: int | None,
    min_score: float | None,
    iv_rank_min: float | None,
    iv_rank_max: float | None,
    price_min: float | None,
    price_max: float | None,
) -> str | None:
    """Return an error message if any numeric filter is out of its documented range.

    Bounds the values forwarded upstream so a caller can't request an unbounded result set
    (response amplification) or send nonsensical filters. Returns ``None`` when all are valid.
    """
    checks = [
        ("limit", limit, 1, 200),
        ("min_score", min_score, 0, 10),
        ("iv_rank_min", iv_rank_min, 0, 100),
        ("iv_rank_max", iv_rank_max, 0, 100),
        ("price_min", price_min, 0, None),
        ("price_max", price_max, 0, None),
    ]
    for name, value, low, high in checks:
        if value is None:
            continue
        if value < low or (high is not None and value > high):
            bound = f"{low}-{high}" if high is not None else f">= {low}"
            return f"`{name}` must be {bound} (got {value})."
    return None


_FILTER_DOC = (
    "Filters (all optional, AND'd): `limit` (1-200, default 20), `min_score` (0-10), `regime` "
    "(CSV of RegimeLabel values like 'trending_low_vol,range_bound'), `recommended_direction` "
    "(CSV of long/short/neutral), `trade_bias`, `trend_state`, `momentum_state`, "
    "`realized_vol_state` (CSV), `iv_rank_min`/`iv_rank_max` (0-100), `price_min`/`price_max`."
)


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="rank_top_setups",
        description=(
            "Rank trade setups across all tickers by opportunity score (descending) to "
            "discover opportunities. " + _FILTER_DOC
        ),
    )
    async def rank_top_setups(
        limit: int | None = None,
        min_score: float | None = None,
        regime: str | None = None,
        recommended_direction: str | None = None,
        trade_bias: str | None = None,
        trend_state: str | None = None,
        momentum_state: str | None = None,
        realized_vol_state: str | None = None,
        iv_rank_min: float | None = None,
        iv_rank_max: float | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
    ) -> dict[str, Any]:
        invalid = _validate_ranking_params(
            limit=limit,
            min_score=min_score,
            iv_rank_min=iv_rank_min,
            iv_rank_max=iv_rank_max,
            price_min=price_min,
            price_max=price_max,
        )
        if invalid:
            return error_envelope("invalid_input", invalid)
        params = _ranking_params(
            limit=limit,
            min_score=min_score,
            regime=regime,
            recommended_direction=recommended_direction,
            trade_bias=trade_bias,
            trend_state=trend_state,
            momentum_state=momentum_state,
            realized_vol_state=realized_vol_state,
            iv_rank_min=iv_rank_min,
            iv_rank_max=iv_rank_max,
            price_min=price_min,
            price_max=price_max,
        )
        return await with_tv(lambda c: c.get_top_setups(params))

    @mcp.tool(
        name="run_screener",
        description=(
            "Run a named screener preset over the cross-ticker ranking. `name` is one of: "
            "momentum_breakout, capitulation_reversal, range_premium_seller, trend_pullback, "
            "highvol_breakdown. Any filter you pass overrides the preset's value. " + _FILTER_DOC
        ),
    )
    async def run_screener(
        name: str,
        limit: int | None = None,
        min_score: float | None = None,
        regime: str | None = None,
        recommended_direction: str | None = None,
        trade_bias: str | None = None,
        trend_state: str | None = None,
        momentum_state: str | None = None,
        realized_vol_state: str | None = None,
        iv_rank_min: float | None = None,
        iv_rank_max: float | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
    ) -> dict[str, Any]:
        preset = name.strip()
        if not preset:
            return error_envelope("invalid_input", "Provide a screener `name`.")
        if not _SCREENER_NAME_RE.fullmatch(preset):
            return error_envelope(
                "invalid_input",
                f"{name!r} is not a valid screener name.",
                "Use one of: momentum_breakout, capitulation_reversal, range_premium_seller, "
                "trend_pullback, highvol_breakdown.",
            )
        invalid = _validate_ranking_params(
            limit=limit,
            min_score=min_score,
            iv_rank_min=iv_rank_min,
            iv_rank_max=iv_rank_max,
            price_min=price_min,
            price_max=price_max,
        )
        if invalid:
            return error_envelope("invalid_input", invalid)
        params = _ranking_params(
            limit=limit,
            min_score=min_score,
            regime=regime,
            recommended_direction=recommended_direction,
            trade_bias=trade_bias,
            trend_state=trend_state,
            momentum_state=momentum_state,
            realized_vol_state=realized_vol_state,
            iv_rank_min=iv_rank_min,
            iv_rank_max=iv_rank_max,
            price_min=price_min,
            price_max=price_max,
        )
        return await with_tv(lambda c: c.run_screener(preset, params))

    @mcp.tool(
        name="rank_income_setups",
        description=(
            "Rank single-leg income setups (covered calls and cash-secured puts) across all "
            "tickers by an IVR-led, regime-guarded income-fit score (descending). Each ticker "
            "may surface as both a CC and a CSP candidate, each with a 1-sigma suggested strike, "
            "estimated premium, annualized yield, assignment/cap price, and breakeven. Filters "
            "(all optional): `type` ('cc' or 'csp'; omit for both), `min_income_score` (0-10), "
            "`limit` (2-50, default 10). Estimates are as-of the latest snapshot; earnings/event "
            "risk is flagged in each row's caveats but not filtered out."
        ),
    )
    async def rank_income_setups(
        type: str | None = None,
        min_income_score: float | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if type is not None:
            strategy = type.strip().lower()
            if strategy not in ("cc", "csp"):
                return error_envelope(
                    "invalid_input",
                    f"{type!r} is not a valid income setup type.",
                    "Use 'cc' (covered call) or 'csp' (cash-secured put), or omit for both.",
                )
            params["type"] = strategy
        if min_income_score is not None:
            if min_income_score < 0 or min_income_score > 10:
                return error_envelope(
                    "invalid_input",
                    f"`min_income_score` must be 0-10 (got {min_income_score}).",
                )
            params["min_income_score"] = min_income_score
        if limit is not None:
            if limit < 2 or limit > 50:
                return error_envelope(
                    "invalid_input", f"`limit` must be 2-50 (got {limit})."
                )
            params["limit"] = limit
        return await with_tv(lambda c: c.get_income_setups(params))

    @mcp.tool(
        name="get_trade_setup",
        description=(
            "Get the compact agent-oriented trade setup for a ticker: market state plus a "
            "deterministic trade recommendation (regime, bias, opportunity score/tier, trade "
            "type, direction, structures, entry/stop/target framing, and caution flags)."
        ),
    )
    async def get_trade_setup(ticker: str) -> dict[str, Any]:
        symbol = normalize_ticker(ticker)
        return await with_tv(lambda c: c.get_trade_setup(symbol), ticker=symbol)

    @mcp.tool(
        name="list_capabilities",
        description=(
            "Return the Trading Volatility v2 capability manifest (the /llm-spec): the full "
            "list of endpoints, metrics, parameters, and conventions. Call this first to "
            "self-orient — to discover which metrics, expirations, regimes, and screeners are "
            "available before making other calls."
        ),
    )
    async def list_capabilities() -> dict[str, Any]:
        return await with_tv(lambda c: c.get_llm_spec())
