"""Tests for require-key mode and configurable retry/timeout (SEC-6, SEC-7)."""

from __future__ import annotations

import httpx
import pytest
import respx

import tv_mcp.tools._common as common
import tv_mcp.tools.auth as auth_tool
from tv_mcp.auth import resolve_request_credential
from tv_mcp.settings import Settings

from .conftest import BASE_URL


async def _call(tool_name: str, **args):
    from tv_mcp.server import create_server

    server = create_server()
    _content, structured = await server.call_tool(tool_name, args)
    return structured


@pytest.fixture
def require_key(monkeypatch):
    """Force TV_REQUIRE_KEY on everywhere the tools read settings."""
    s = Settings(tv_api_key=None, tv_config_file=None, tv_require_key=True)
    monkeypatch.setattr(common, "get_settings", lambda: s)
    monkeypatch.setattr(auth_tool, "get_settings", lambda: s)
    return s


@respx.mock
async def test_require_key_rejects_anonymous_call(require_key):
    route = respx.get(url__regex=rf"{BASE_URL}.*").mock(
        return_value=httpx.Response(200, json={"ticker": "AAPL"})
    )
    data = await _call("get_ticker_state", ticker="AAPL")  # AAPL is a demo ticker
    assert data["error"]["reason"] == "missing_credentials"
    assert route.call_count == 0  # rejected before any upstream request


@respx.mock
async def test_require_key_allows_keyed_call(require_key, with_api_key):
    respx.get(f"{BASE_URL}/tickers/AAPL").mock(
        return_value=httpx.Response(200, json={"ticker": "AAPL"})
    )
    data = await _call("get_ticker_state", ticker="AAPL")
    assert data["ticker"] == "AAPL"


async def test_auth_status_reports_key_required(require_key):
    data = await _call("get_auth_status")
    assert data["mode"] == "key_required"


def test_credential_carries_configured_retries_and_timeout(monkeypatch):
    import tv_mcp.auth as auth_mod

    s = Settings(tv_api_key="k", tv_config_file=None, tv_max_retries=1, tv_request_timeout=7.0)
    monkeypatch.setattr(auth_mod, "get_settings", lambda: s)
    cred = resolve_request_credential()
    assert cred.max_retries == 1
    assert cred.timeout == 7.0
