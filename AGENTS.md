# Trading Volatility MCP — for AI agents

This is a [Model Context Protocol](https://modelcontextprotocol.io) server that gives agents
read-only access to [Trading Volatility](https://stocks.tradingvolatility.net) options
market-structure data: GEX, gamma flip levels, dealer positioning, volatility skew, max pain,
expected-move levels, options volume, and cross-ticker ranked trade setups.

It is a stateless passthrough over the public
[v2 API](https://stocks.tradingvolatility.net/api/v2/docs) — it discovers and retrieves data,
and never places orders or takes payments.

## Connect

- **Endpoint:** `POST <this-server>/mcp` — Streamable HTTP + SSE (standard MCP transport).
- **Auth:** send your Trading Volatility API key as `Authorization: Bearer <key>`
  (`X-Api-Key: <key>` also works).
- **No key?** The demo tickers — AAPL, VIX, KO, META, AMZN, XOM, GM, MCD — work without one.
- **Local:** `uvx tv-mcp` runs the same server over stdio.

## First call

Call **`list_capabilities`** first. It returns the v2 `/llm-spec` manifest — the full set of
endpoints, metrics, expirations, regimes, and screener names — so you can self-orient before
querying. Call `get_auth_status` to see whether you're in keyed or demo mode.

## Tools

| Tool | Returns |
|------|---------|
| `list_capabilities` | The v2 capability manifest (`/llm-spec`) — call first |
| `get_auth_status` | Whether you're in keyed or demo mode |
| `get_ticker_state` | Canonical compact state snapshot for a ticker |
| `explain_ticker` | Deterministic narrative interpretation of the regime |
| `get_market_structure` | Headline signal, regime, expected behavior, levels |
| `get_signals` | Current setup/positioning signals |
| `get_levels` | Key levels (json / tradingview / tos) |
| `get_series` | Historical daily series for selected metrics over a window |
| `get_gamma_curve` | Gamma strike curve (per expiration, optionally realtime) |
| `get_gamma_by_expiration` | Gamma decomposition by expiration bucket |
| `get_gex_by_strike` | Net GEX strike curve with call/put contributions |
| `get_options_volume` | Options volume by strike for an expiration |
| `rank_top_setups` | Cross-ticker opportunity ranking, with filters |
| `run_screener` | A named thesis preset over the ranking |
| `rank_income_setups` | Cross-ticker covered-call / cash-secured-put ranking, with filters |
| `get_trade_setup` | Compact agent-oriented trade setup for one ticker |

All tools return the v2 JSON payloads unchanged (already agent-shaped). Failures come back as a
uniform `{"error": {"reason", "message", "suggestion?"}}` envelope — e.g. `not_found`,
`rate_limited`, `invalid_credentials`, `missing_credentials`.

## Integration guides

Per-framework setup (Claude, OpenAI, Gemini, Google ADK, LangChain/LangGraph, Vercel AI SDK)
is in the repository's `docs/integrations/`. Any MCP-capable client works: point it at
`/mcp` and pass the `Authorization: Bearer` header.
