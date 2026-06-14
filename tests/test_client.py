"""Tests for the TV API client: auth headers, error mapping, retries (T0.4)."""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

import tv_mcp.auth as auth
import tv_mcp.tv.client as client_mod
from tv_mcp.auth import resolve_request_credential
from tv_mcp.tv.client import TVClient
from tv_mcp.tv.errors import TVNotFoundError, TVRateLimitError

from .conftest import BASE_URL


@respx.mock
async def test_bearer_header_sent_when_keyed():
    route = respx.get(f"{BASE_URL}/tickers/AAPL").mock(
        return_value=httpx.Response(200, json={"ticker": "AAPL"})
    )
    async with TVClient(api_key="k") as client:
        result = await client.get_ticker_state("AAPL")
    assert result == {"ticker": "AAPL"}
    assert route.calls.last.request.headers["authorization"] == "Bearer k"
    assert "x-tv-demo" not in route.calls.last.request.headers


@respx.mock
async def test_demo_header_sent_when_no_key():
    route = respx.get(f"{BASE_URL}/tickers/AAPL").mock(
        return_value=httpx.Response(200, json={"ticker": "AAPL"})
    )
    async with TVClient(api_key=None) as client:
        await client.get_ticker_state("AAPL")
    assert route.calls.last.request.headers["x-tv-demo"] == "1"
    assert "authorization" not in route.calls.last.request.headers


@respx.mock
async def test_none_params_dropped():
    route = respx.get(f"{BASE_URL}/tickers/AAPL/series").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    async with TVClient(api_key="k") as client:
        await client.get_series("AAPL", metrics="price", window=None)
    assert route.calls.last.request.url.params["metrics"] == "price"
    assert "window" not in route.calls.last.request.url.params


@respx.mock
async def test_404_maps_to_not_found():
    respx.get(f"{BASE_URL}/tickers/ZZZZ").mock(return_value=httpx.Response(404, text="nope"))
    async with TVClient(api_key="k") as client:
        with pytest.raises(TVNotFoundError):
            await client.get_ticker_state("ZZZZ")


@respx.mock
async def test_429_retries_then_succeeds():
    route = respx.get(f"{BASE_URL}/tickers/AAPL").mock(
        side_effect=[
            httpx.Response(429, headers={"retry-after": "0"}),
            httpx.Response(200, json={"ticker": "AAPL"}),
        ]
    )
    async with TVClient(api_key="k", retry_backoff=0) as client:
        result = await client.get_ticker_state("AAPL")
    assert result == {"ticker": "AAPL"}
    assert route.call_count == 2


@respx.mock
async def test_429_exhausts_retries():
    respx.get(f"{BASE_URL}/tickers/AAPL").mock(
        return_value=httpx.Response(429, headers={"retry-after": "0"})
    )
    async with TVClient(api_key="k", retry_backoff=0, max_retries=1) as client:
        with pytest.raises(TVRateLimitError):
            await client.get_ticker_state("AAPL")


@respx.mock
async def test_304_returns_none():
    respx.get(f"{BASE_URL}/top-setups").mock(return_value=httpx.Response(304))
    async with TVClient(api_key="k") as client:
        assert await client.get_top_setups() is None


@respx.mock
async def test_pooled_client_reused_without_key_bleed():
    """With pooling on, concurrent calls share one client but each sends its own key."""
    route = respx.get(f"{BASE_URL}/tickers/AAPL").mock(
        return_value=httpx.Response(200, json={"ticker": "AAPL"})
    )
    client_mod.enable_connection_pool()
    try:

        async def call(key: str):
            token = auth.current_request_api_key.set(key)
            try:
                async with resolve_request_credential().client() as c:
                    await c.get_ticker_state("AAPL")
            finally:
                auth.current_request_api_key.reset(token)

        await asyncio.gather(call("KEY_A"), call("KEY_B"))

        sent = sorted(c.request.headers["authorization"] for c in route.calls)
        assert sent == ["Bearer KEY_A", "Bearer KEY_B"]  # no cross-request key bleed
        assert len(client_mod._pooled_clients) == 1  # one client actually reused
    finally:
        await client_mod.aclose_pooled_clients()
        client_mod._pool_enabled = False
