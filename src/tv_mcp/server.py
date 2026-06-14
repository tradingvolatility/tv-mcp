"""MCP server core.

Builds the ``FastMCP`` instance, configures it for stateless HTTP + SSE transport, and
registers tools and resources. Tool modules each expose a ``register(mcp)`` function; this
module wires them together. The server holds no per-session state (``stateless_http=True``).
"""

from __future__ import annotations

import importlib.resources
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from . import __version__
from .auth import resolve_request_credential
from .settings import get_settings
from .tools import auth as auth_tools
from .tools import curves as curves_tools
from .tools import discovery as discovery_tools
from .tools import tickers as tickers_tools
from .tools._common import error_envelope
from .tv.errors import TVError

SERVER_NAME = "tv-mcp"
INSTRUCTIONS = (
    "Trading Volatility options & volatility data. Discover and retrieve options "
    "market-structure data conversationally: ticker state snapshots, deterministic "
    "explanations, signals, market structure, key levels, historical series, gamma and GEX "
    "strike curves, options volume, and cross-ticker ranked trade setups. Read-only — this "
    "server never places orders or takes payments. Call list_capabilities first to discover "
    "the available metrics, expirations, regimes, and screeners. Without an API key only the "
    "demo tickers (AAPL, VIX, KO, META, AMZN, XOM, GM, MCD) are available; check "
    "get_auth_status to see the current mode."
)


def register_builtin_tools(mcp: FastMCP) -> None:
    """Register server-level tools that don't belong to a TV domain module."""

    @mcp.tool(name="server_info", description="Basic information about this MCP server.")
    def server_info() -> dict[str, str]:
        return {"name": SERVER_NAME, "version": __version__}


def register_resources(mcp: FastMCP) -> None:
    """Expose the v2 capability manifest as an MCP resource (T1.4).

    Mirrors the ``list_capabilities`` tool as a resource so clients that browse resources can
    load the spec for grounding. Uses the request credential (or demo mode).
    """

    @mcp.resource(
        "tv://llm-spec",
        name="Trading Volatility v2 capability manifest",
        description="The /llm-spec manifest: endpoints, metrics, parameters, and conventions.",
        mime_type="application/json",
    )
    async def llm_spec_resource() -> str:
        # Unlike the tools, a resource read returns a string, so map upstream failures to a
        # JSON error payload here rather than letting an exception escape as a ResourceError.
        credential = resolve_request_credential()
        if credential.is_demo and get_settings().tv_require_key:
            return json.dumps(
                error_envelope(
                    "missing_credentials",
                    "This server requires a Trading Volatility API key.",
                    "Send your key as an Authorization: Bearer <key> header.",
                ),
                indent=2,
            )
        try:
            async with credential.client() as client:
                spec = await client.get_llm_spec()
        except TVError as exc:
            return json.dumps(error_envelope("error", str(exc)), indent=2)
        except Exception:
            return json.dumps(
                error_envelope("error", "An unexpected error occurred loading the manifest."),
                indent=2,
            )
        return json.dumps(spec, indent=2)


def _load_agents_md() -> str:
    """Load the agent-discovery markdown, robust across container and editable installs.

    In a built wheel / container it's packaged as ``tv_mcp/AGENTS.md`` (pyproject
    force-include); in an editable dev checkout it's the repo-root ``AGENTS.md``. Returns ""
    if neither is found, in which case the route 404s.
    """
    try:
        resource = importlib.resources.files("tv_mcp").joinpath("AGENTS.md")
        if resource.is_file():
            return resource.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError):
        pass
    root_copy = Path(__file__).resolve().parents[2] / "AGENTS.md"  # src/tv_mcp/server.py -> repo
    if root_copy.is_file():
        return root_copy.read_text(encoding="utf-8")
    return ""


def register_discovery(mcp: FastMCP) -> None:
    """Serve ``/AGENTS.md`` so agents discovering the endpoint can read how to use it."""
    agents_md = _load_agents_md()

    @mcp.custom_route("/AGENTS.md", methods=["GET"])
    async def agents_md_route(_request: Request) -> Response:
        if not agents_md:
            return PlainTextResponse("AGENTS.md not found", status_code=404)
        return PlainTextResponse(agents_md, media_type="text/markdown; charset=utf-8")


def register_health(mcp: FastMCP) -> None:
    """Expose a liveness endpoint for hosted deployments.

    Served on both ``/health`` and ``/healthz`` (T2.2). Cloud Run's edge reserves paths ending
    in ``z`` and may not route ``/healthz`` to the container, so ``/health`` is the
    externally-reachable path there; ``/healthz`` is kept for local/Kubernetes conventions.
    The handler is plain and unauthenticated; it omits the version so the public probe doesn't
    fingerprint the build (the version is available via the server_info tool, which needs an
    MCP session).
    """

    async def _health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": SERVER_NAME})

    mcp.custom_route("/health", methods=["GET"])(_health)
    mcp.custom_route("/healthz", methods=["GET"])(_health)


def create_server() -> FastMCP:
    """Construct and configure the Trading Volatility MCP server with everything registered."""
    settings = get_settings()
    mcp = FastMCP(
        name=SERVER_NAME,
        instructions=INSTRUCTIONS,
        stateless_http=True,
        log_level=settings.log_level.upper(),
        host=settings.host,
        port=settings.port,
    )
    register_builtin_tools(mcp)
    register_health(mcp)
    register_discovery(mcp)
    register_resources(mcp)
    auth_tools.register(mcp)
    tickers_tools.register(mcp)
    curves_tools.register(mcp)
    discovery_tools.register(mcp)
    return mcp
