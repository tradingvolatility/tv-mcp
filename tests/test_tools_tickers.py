"""Tests for the ticker-state tools (T1.1, T1.5): happy / 404 / demo paths."""

from __future__ import annotations

import httpx
import respx

from tv_mcp.server import create_server

from .conftest import BASE_URL


async def _call(tool_name: str, **args):
    server = create_server()
    return await server.call_tool(tool_name, args)


def _payload(result):
    """FastMCP returns (content, structured) from call_tool; return the structured dict."""
    _content, structured = result
    return structured


@respx.mock
async def test_get_ticker_state_happy(with_api_key):
    respx.get(f"{BASE_URL}/tickers/AAPL").mock(
        return_value=httpx.Response(200, json={"ticker": "AAPL", "price": 200})
    )
    data = _payload(await _call("get_ticker_state", ticker="aapl"))
    assert data["ticker"] == "AAPL"
    assert data["price"] == 200


@respx.mock
async def test_get_ticker_state_not_found(with_api_key):
    respx.get(f"{BASE_URL}/tickers/ZZZZ").mock(return_value=httpx.Response(404, text="no"))
    data = _payload(await _call("get_ticker_state", ticker="ZZZZ"))
    assert data["error"]["reason"] == "not_found"


@respx.mock
async def test_demo_supported_ticker_works():
    # No api key (demo). AAPL is a demo ticker, so the call goes through.
    respx.get(f"{BASE_URL}/tickers/AAPL").mock(
        return_value=httpx.Response(200, json={"ticker": "AAPL"})
    )
    data = _payload(await _call("get_ticker_state", ticker="AAPL"))
    assert data["ticker"] == "AAPL"


@respx.mock
async def test_demo_unsupported_ticker_reports_missing_credentials():
    # No api key + non-demo ticker → API 401 → friendly missing_credentials envelope.
    respx.get(f"{BASE_URL}/tickers/TSLA").mock(return_value=httpx.Response(401, text="auth"))
    data = _payload(await _call("get_ticker_state", ticker="TSLA"))
    assert data["error"]["reason"] == "missing_credentials"
    assert "demo" in data["error"]["message"].lower()


@respx.mock
async def test_get_levels_passes_view(with_api_key):
    route = respx.get(f"{BASE_URL}/tickers/AAPL/levels").mock(
        return_value=httpx.Response(200, json={"levels": []})
    )
    await _call("get_levels", ticker="AAPL", view="tos")
    assert route.calls.last.request.url.params["view"] == "tos"
