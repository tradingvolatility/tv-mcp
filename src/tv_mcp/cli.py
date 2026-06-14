"""Command-line entry point for the Trading Volatility MCP server.

Two transports ship in v1:

- ``stdio`` (default) — how local agent clients (Claude Desktop, ``uvx tv-mcp``, etc.) launch
  the server. Credentials come from ``TV_API_KEY`` or the local JSON config.
- ``http`` — the stateless streamable HTTP + SSE server for remote, multi-user hosting.
  Credentials arrive per request via the ``Authorization`` / ``X-Api-Key`` header.

Pick the transport with ``--transport`` or the ``TV_MCP_TRANSPORT`` env var (CLI wins).
"""

from __future__ import annotations

import argparse

from .logging_setup import configure_logging
from .server import create_server
from .settings import get_settings


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="tv-mcp", description="Trading Volatility MCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=None,
        help="Transport to serve (default: TV_MCP_TRANSPORT or 'stdio').",
    )
    parser.add_argument("--host", default=None, help="HTTP bind host (default: settings/HOST).")
    parser.add_argument(
        "--port", type=int, default=None, help="HTTP bind port (default: settings/PORT)."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)

    transport = args.transport or settings.tv_mcp_transport
    server = create_server()

    if transport == "stdio":
        server.run(transport="stdio")
        return

    # HTTP: serve our own ASGI app so the per-request auth-header middleware, CORS, and the
    # /healthz route are included (FastMCP.run would build its own app and bypass them).
    import uvicorn

    from .transports.http import build_http_app
    from .tv.client import enable_connection_pool

    # Reuse one upstream connection per base_url across requests (avoids a TLS handshake per
    # call). Safe because credentials are sent per request, not stored on the client.
    enable_connection_pool()
    app = build_http_app(server)
    uvicorn.run(
        app,
        host=args.host or settings.host,
        port=args.port or settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
