"""Tests for tool-boundary input validation and client-side path encoding.

These cover the security hardening: caller input (tickers, screener names) must never reach
the upstream URL path in a form that could inject segments, traverse with '..', or smuggle
query params. Validation happens before any request is built; encoding is the backstop.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from tv_mcp.server import create_server
from tv_mcp.tools._common import is_valid_ticker
from tv_mcp.tv.client import _seg

from .conftest import BASE_URL


async def _call(tool_name: str, **args):
    server = create_server()
    _content, structured = await server.call_tool(tool_name, args)
    return structured


# --- ticker validation -------------------------------------------------------


@pytest.mark.parametrize("symbol", ["AAPL", "BRK.B", "^VIX", "ES=F", "SPX", "A"])
def test_valid_tickers_accepted(symbol):
    assert is_valid_ticker(symbol)


@pytest.mark.parametrize(
    "symbol",
    [
        "../../llm-spec",  # path traversal
        "foo/bar",  # injected segment
        "AAPL?admin=1",  # query smuggling
        "AAPL#x",  # fragment
        "AAPL ",  # whitespace (pre-normalized form)
        "",  # empty
        "A" * 17,  # too long
        "DROP TABLE",  # space
    ],
)
def test_invalid_tickers_rejected(symbol):
    assert not is_valid_ticker(symbol)


@respx.mock
async def test_traversal_ticker_rejected_without_network():
    # A traversal attempt must be rejected at the boundary — no HTTP request is made.
    route = respx.get(url__regex=rf"{BASE_URL}.*").mock(
        return_value=httpx.Response(200, json={})
    )
    data = await _call("get_ticker_state", ticker="../../llm-spec")
    assert data["error"]["reason"] == "invalid_input"
    assert route.call_count == 0


# --- screener name validation ------------------------------------------------


@respx.mock
async def test_screener_traversal_name_rejected_without_network():
    route = respx.get(url__regex=rf"{BASE_URL}.*").mock(
        return_value=httpx.Response(200, json={})
    )
    data = await _call("run_screener", name="../../../agent/trade-setup/AAPL")
    assert data["error"]["reason"] == "invalid_input"
    assert route.call_count == 0


# --- options volume required exp ---------------------------------------------


@respx.mock
async def test_options_volume_empty_exp_rejected(with_api_key):
    route = respx.get(url__regex=rf"{BASE_URL}.*").mock(
        return_value=httpx.Response(200, json={})
    )
    data = await _call("get_options_volume", ticker="AAPL", exp="  ")
    assert data["error"]["reason"] == "invalid_input"
    assert route.call_count == 0


# --- client-side path encoding (defense in depth) ----------------------------


def test_seg_encodes_path_separators_and_traversal():
    assert _seg("../../x") == "..%2F..%2Fx"
    assert _seg("foo/bar") == "foo%2Fbar"
    assert _seg("a?b#c") == "a%3Fb%23c"
    # Unreserved characters common in symbols are left intact.
    assert _seg("BRK.B") == "BRK.B"
