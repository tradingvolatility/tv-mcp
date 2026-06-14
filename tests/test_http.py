"""Tests for the HTTP transport: header extraction and per-request scoping (T2.1)."""

from __future__ import annotations

from tv_mcp.auth import current_request_api_key
from tv_mcp.transports.http import (
    ApiKeyHeaderMiddleware,
    MaxBodySizeMiddleware,
    _extract_api_key,
)


def _scope(headers: dict[str, str]) -> dict:
    return {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }


def _body_receiver(chunks: list[bytes]):
    """An ASGI receive() that yields the given body chunks as http.request messages."""
    queue = list(chunks)

    async def receive():
        body = queue.pop(0)
        return {"type": "http.request", "body": body, "more_body": bool(queue)}

    return receive


class _Recorder:
    def __init__(self):
        self.messages = []

    async def __call__(self, message):
        self.messages.append(message)

    @property
    def status(self):
        for m in self.messages:
            if m["type"] == "http.response.start":
                return m["status"]
        return None


def test_extract_bearer():
    assert _extract_api_key(_scope({"Authorization": "Bearer abc123"})) == "abc123"


def test_extract_bearer_case_insensitive():
    assert _extract_api_key(_scope({"Authorization": "bearer abc123"})) == "abc123"


def test_extract_raw_authorization_without_bearer():
    assert _extract_api_key(_scope({"Authorization": "abc123"})) == "abc123"


def test_extract_x_api_key_fallback():
    assert _extract_api_key(_scope({"X-Api-Key": "xyz"})) == "xyz"


def test_authorization_beats_x_api_key():
    scope = _scope({"Authorization": "Bearer abc", "X-Api-Key": "xyz"})
    assert _extract_api_key(scope) == "abc"


def test_extract_none_when_absent():
    assert _extract_api_key(_scope({})) is None


async def test_health_routes_registered():
    """Both /health and /healthz are exposed (Cloud Run can't route /healthz)."""
    from tv_mcp.server import create_server

    server = create_server()
    app = server.streamable_http_app()
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/health" in paths
    assert "/healthz" in paths


async def test_agents_md_route_registered_and_loads():
    """/AGENTS.md is exposed and the discovery content loads (non-empty)."""
    from tv_mcp.server import _load_agents_md, create_server

    assert "Trading Volatility MCP" in _load_agents_md()
    server = create_server()
    app = server.streamable_http_app()
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/AGENTS.md" in paths


async def test_body_size_rejects_oversized():
    async def app(scope, receive, send):  # should never run
        raise AssertionError("oversized body reached the app")

    mw = MaxBodySizeMiddleware(app, max_bytes=10)
    rec = _Recorder()
    await mw(_scope({}), _body_receiver([b"x" * 50]), rec)
    assert rec.status == 413


async def test_body_size_passes_small_body_through():
    seen = {}

    async def app(scope, receive, send):
        msg = await receive()
        seen["body"] = msg["body"]

    mw = MaxBodySizeMiddleware(app, max_bytes=1024)
    await mw(_scope({}), _body_receiver([b"hello"]), _Recorder())
    assert seen["body"] == b"hello"


async def test_middleware_sets_and_resets_contextvar():
    seen = {}

    async def app(scope, receive, send):
        seen["key"] = current_request_api_key.get()

    mw = ApiKeyHeaderMiddleware(app)
    await mw(_scope({"Authorization": "Bearer per-req"}), None, None)
    assert seen["key"] == "per-req"
    # Reset after the request: no leakage to the next caller.
    assert current_request_api_key.get() is None
