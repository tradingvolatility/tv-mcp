"""Stateless HTTP + SSE transport (T2.1, T2.2).

Exposes the MCP server as an ASGI app using the Streamable HTTP transport, which serves
request/response over HTTP and streams longer-running results over SSE. Mounted at ``/mcp``.

In hosted mode, ``ApiKeyHeaderMiddleware`` reads the per-request credential from the
``Authorization: Bearer <key>`` header (falling back to ``X-Api-Key``) into a context
variable and resets it after the request, so each request is scoped to its own account with
no cross-request credential leakage. The server keeps no session state (``stateless_http``).
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware

from ..auth import current_request_api_key
from ..settings import API_KEY_HEADER, AUTH_HEADER, get_settings

_AUTH_HEADER_BYTES = AUTH_HEADER.lower().encode()
_API_KEY_HEADER_BYTES = API_KEY_HEADER.lower().encode()
_BEARER_PREFIX = "bearer "


def _extract_api_key(scope: dict) -> str | None:
    """Pull the caller's API key from the request headers.

    Prefers ``Authorization: Bearer <key>`` (the v2 API's primary scheme); falls back to
    ``X-Api-Key``. Returns ``None`` when neither is present (demo mode).
    """
    auth_value: str | None = None
    api_key_value: str | None = None
    # First occurrence wins, so a smuggled second Authorization/X-Api-Key header can't override
    # the one the edge/proxy validated.
    for name, value in scope.get("headers", []):
        if name == _AUTH_HEADER_BYTES and auth_value is None:
            auth_value = value.decode("latin-1")
        elif name == _API_KEY_HEADER_BYTES and api_key_value is None:
            api_key_value = value.decode("latin-1")
    if auth_value:
        if auth_value.lower().startswith(_BEARER_PREFIX):
            return auth_value[len(_BEARER_PREFIX) :].strip() or None
        return auth_value.strip() or None
    if api_key_value:
        return api_key_value.strip() or None
    return None


async def _send_413(send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": b'{"error":"request body too large"}'})


class MaxBodySizeMiddleware:
    """Reject oversized request bodies with 413 before the app buffers them.

    MCP JSON-RPC requests are tiny, so we buffer the body up to the cap and replay it to the
    app; anything larger is refused. Caps memory under load and blocks body-amplification
    abuse. ``max_bytes <= 0`` disables the check.
    """

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or self.max_bytes <= 0:
            await self.app(scope, receive, send)
            return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] != "http.request":
                # Forward non-body messages (e.g. http.disconnect) and stop buffering.
                await self.app(scope, _prepend(message, receive), send)
                return
            body += message.get("body", b"")
            if len(body) > self.max_bytes:
                await _send_413(send)
                return
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay_receive():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)


def _prepend(first, receive):
    """Return a receive callable that yields ``first`` once, then delegates to ``receive``."""
    sent = False

    async def _receive():
        nonlocal sent
        if not sent:
            sent = True
            return first
        return await receive()

    return _receive


class ApiKeyHeaderMiddleware:
    """ASGI middleware that scopes the caller's API key to the current request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        token = current_request_api_key.set(_extract_api_key(scope))
        try:
            await self.app(scope, receive, send)
        finally:
            current_request_api_key.reset(token)


def build_http_app(mcp: FastMCP):
    """Return the ASGI application for the Streamable HTTP (HTTP + SSE) transport."""
    settings = get_settings()
    origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
    app = ApiKeyHeaderMiddleware(mcp.streamable_http_app())
    app = MaxBodySizeMiddleware(app, max_bytes=settings.tv_max_request_bytes)
    # Browser-based MCP clients need CORS; expose the SSE/session headers they read.
    return CORSMiddleware(
        app,
        allow_origins=origins or ["*"],
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
