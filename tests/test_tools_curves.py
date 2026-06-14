"""Tests for the curve/series tools (T1.2, T1.5)."""

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
async def test_gamma_curve_forwards_exp_and_realtime(with_api_key):
    route = respx.get(f"{BASE_URL}/tickers/AAPL/curves/gamma").mock(
        return_value=httpx.Response(200, json={"curve": []})
    )
    await _call("get_gamma_curve", ticker="AAPL", exp="nearest", realtime=True)
    params = route.calls.last.request.url.params
    assert params["exp"] == "nearest"
    assert params["realtime"] == "true"


@respx.mock
async def test_gex_by_strike_default_exp_omitted(with_api_key):
    route = respx.get(f"{BASE_URL}/tickers/AAPL/curves/gex_by_strike").mock(
        return_value=httpx.Response(200, json={"curve": []})
    )
    await _call("get_gex_by_strike", ticker="AAPL")
    assert "exp" not in route.calls.last.request.url.params


@respx.mock
async def test_options_volume_requires_exp(with_api_key):
    route = respx.get(f"{BASE_URL}/tickers/AAPL/options/volume").mock(
        return_value=httpx.Response(200, json={"volume": []})
    )
    await _call("get_options_volume", ticker="AAPL", exp="2026-06-19", include="iv")
    params = route.calls.last.request.url.params
    assert params["exp"] == "2026-06-19"
    assert params["include"] == "iv"


@respx.mock
async def test_gamma_by_expiration(with_api_key):
    respx.get(f"{BASE_URL}/tickers/AAPL/curves/gamma/expirations").mock(
        return_value=httpx.Response(200, json={"buckets": ["combined", "nearest"]})
    )
    data = await _call("get_gamma_by_expiration", ticker="AAPL")
    assert data["buckets"] == ["combined", "nearest"]
