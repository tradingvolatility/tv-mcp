"""Smoke tests: the server builds and exposes the expected tools and resources."""

from __future__ import annotations

from tv_mcp.server import create_server

EXPECTED_TOOLS = {
    "server_info",
    "get_auth_status",
    "get_ticker_state",
    "explain_ticker",
    "get_market_structure",
    "get_signals",
    "get_levels",
    "get_series",
    "get_gamma_curve",
    "get_gamma_by_expiration",
    "get_gex_by_strike",
    "get_options_volume",
    "rank_top_setups",
    "run_screener",
    "rank_income_setups",
    "get_trade_setup",
    "list_capabilities",
}


async def test_all_tools_registered():
    server = create_server()
    tools = await server.list_tools()
    assert {t.name for t in tools} == EXPECTED_TOOLS


async def test_spec_resource_registered():
    server = create_server()
    resources = await server.list_resources()
    assert any(str(r.uri) == "tv://llm-spec" for r in resources)


async def test_server_info_tool():
    server = create_server()
    _content, structured = await server.call_tool("server_info", {})
    assert structured["name"] == "tv-mcp"
