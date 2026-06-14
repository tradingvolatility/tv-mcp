"""Tests for the discovery/ranking/capability tools (T1.3, T1.4, T1.5)."""

from __future__ import annotations

import httpx
import respx

from tv_mcp.server import create_server

from .conftest import BASE_URL


async def _call(tool_name: str, **args):
    server = create_server()
    _content, structured = await server.call_tool(tool_name, args)
    return structured


@respx.mock
async def test_rank_top_setups_forwards_filters(with_api_key):
    route = respx.get(f"{BASE_URL}/top-setups").mock(
        return_value=httpx.Response(200, json={"rows": []})
    )
    await _call("rank_top_setups", limit=5, min_score=2.5, recommended_direction="long")
    params = route.calls.last.request.url.params
    assert params["limit"] == "5"
    assert params["min_score"] == "2.5"
    assert params["recommended_direction"] == "long"


@respx.mock
async def test_rank_top_setups_omits_unset(with_api_key):
    route = respx.get(f"{BASE_URL}/top-setups").mock(
        return_value=httpx.Response(200, json={"rows": []})
    )
    await _call("rank_top_setups", limit=10)
    params = route.calls.last.request.url.params
    assert params["limit"] == "10"
    assert "min_score" not in params
    assert "regime" not in params


@respx.mock
async def test_run_screener_uses_name_in_path(with_api_key):
    route = respx.get(f"{BASE_URL}/top-setups/screener/momentum_breakout").mock(
        return_value=httpx.Response(200, json={"rows": []})
    )
    await _call("run_screener", name="momentum_breakout", limit=3)
    assert route.call_count == 1
    assert route.calls.last.request.url.params["limit"] == "3"


async def test_run_screener_empty_name_is_invalid_input(with_api_key):
    data = await _call("run_screener", name="  ")
    assert data["error"]["reason"] == "invalid_input"


@respx.mock
async def test_rank_top_setups_rejects_out_of_range_limit(with_api_key):
    route = respx.get(url__regex=rf"{BASE_URL}.*").mock(
        return_value=httpx.Response(200, json={"rows": []})
    )
    data = await _call("rank_top_setups", limit=10_000_000)
    assert data["error"]["reason"] == "invalid_input"
    assert route.call_count == 0


@respx.mock
async def test_rank_top_setups_rejects_bad_iv_rank(with_api_key):
    route = respx.get(url__regex=rf"{BASE_URL}.*").mock(
        return_value=httpx.Response(200, json={"rows": []})
    )
    data = await _call("rank_top_setups", iv_rank_max=500)
    assert data["error"]["reason"] == "invalid_input"
    assert route.call_count == 0


@respx.mock
async def test_run_screener_unknown_preset_404(with_api_key):
    respx.get(f"{BASE_URL}/top-setups/screener/bogus").mock(
        return_value=httpx.Response(404, text="unknown preset")
    )
    data = await _call("run_screener", name="bogus")
    assert data["error"]["reason"] == "not_found"


@respx.mock
async def test_get_trade_setup(with_api_key):
    respx.get(f"{BASE_URL}/agent/trade-setup/AAPL").mock(
        return_value=httpx.Response(200, json={"data": {"ticker": "AAPL"}})
    )
    data = await _call("get_trade_setup", ticker="aapl")
    assert data["data"]["ticker"] == "AAPL"


@respx.mock
async def test_list_capabilities(with_api_key):
    respx.get(f"{BASE_URL}/llm-spec").mock(
        return_value=httpx.Response(200, json={"endpoints": ["/tickers/{ticker}"]})
    )
    data = await _call("list_capabilities")
    assert "endpoints" in data
