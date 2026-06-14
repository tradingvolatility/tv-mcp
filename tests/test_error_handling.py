"""Tests for the error-handling contract (review findings N1-N4).

The guarantee under test: a tool call always returns a result/envelope and never raises, and
the llm-spec resource returns a JSON error payload instead of raising — even when the upstream
returns a non-JSON success body, an empty success body, or fails outright.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from tv_mcp.server import create_server
from tv_mcp.tv.client import TVClient
from tv_mcp.tv.errors import TVServerError

from .conftest import BASE_URL


async def _call(tool_name: str, **args):
    server = create_server()
    _content, structured = await server.call_tool(tool_name, args)
    return structured


# --- N1: non-JSON success body -----------------------------------------------


@respx.mock
async def test_client_raises_tvservererror_on_non_json_success():
    respx.get(f"{BASE_URL}/tickers/AAPL").mock(
        return_value=httpx.Response(200, text="<html>challenge</html>")
    )
    async with TVClient(api_key="k") as client:
        with pytest.raises(TVServerError):
            await client.get_ticker_state("AAPL")


@respx.mock
async def test_tool_returns_envelope_on_non_json_success(with_api_key):
    respx.get(f"{BASE_URL}/tickers/AAPL").mock(
        return_value=httpx.Response(200, text="<html>challenge</html>")
    )
    data = await _call("get_ticker_state", ticker="AAPL")
    assert data["error"]["reason"] == "error"


# --- N2: empty success body --------------------------------------------------


@respx.mock
async def test_tool_coerces_empty_success_to_dict(with_api_key):
    respx.get(f"{BASE_URL}/tickers/AAPL").mock(return_value=httpx.Response(200, content=b""))
    data = await _call("get_ticker_state", ticker="AAPL")
    assert data == {}


@respx.mock
async def test_tool_handles_304(with_api_key):
    respx.get(f"{BASE_URL}/tickers/AAPL").mock(return_value=httpx.Response(304))
    data = await _call("get_ticker_state", ticker="AAPL")
    assert data == {}


# --- N3: resource handler maps errors instead of raising ---------------------


@respx.mock
async def test_resource_returns_error_payload_on_non_json(with_api_key):
    respx.get(f"{BASE_URL}/llm-spec").mock(return_value=httpx.Response(200, text="oops"))
    server = create_server()
    result = await server.read_resource("tv://llm-spec")
    # FastMCP returns an iterable of ReadResourceContents; take the first payload.
    payload = next(iter(result)).content
    assert json.loads(payload)["error"]["reason"] == "error"


@respx.mock
async def test_resource_returns_error_payload_on_auth_failure(with_api_key):
    respx.get(f"{BASE_URL}/llm-spec").mock(return_value=httpx.Response(401, text="nope"))
    server = create_server()
    result = await server.read_resource("tv://llm-spec")
    payload = next(iter(result)).content
    assert "error" in json.loads(payload)
