# Trading Volatility MCP

**The options & volatility data source agents can query.**

A [Model Context Protocol](https://modelcontextprotocol.io) server for
[Trading Volatility](https://stocks.tradingvolatility.net) — lets any AI agent discover and
retrieve options market-structure data (GEX, gamma flip levels, dealer positioning, skew,
max pain, expected-move levels, options flow, and ranked trade setups) over the public
[v2 API](https://stocks.tradingvolatility.net/api/v2/docs), in conversation.

- **Read-only** — discovers and retrieves data over your existing Trading Volatility
  subscription. No orders, payments, or monitoring.
- **Stateless passthrough** — forwards your `Authorization: Bearer <key>` to the v2 API and
  stores nothing. Local and hosted modes are the same code path.
- **Two transports** — `stdio` for local agents, streamable **HTTP + SSE** for remote,
  multi-user hosting.
- **Works without a key** — the demo tickers (AAPL, VIX, KO, META, AMZN, XOM, GM, MCD) work
  out of the box.

## Tools

| Tool | What it returns |
|------|-----------------|
| `list_capabilities` | The v2 capability manifest (`/llm-spec`) — call first to self-orient |
| `get_auth_status` | Whether you're in keyed or demo mode |
| `get_ticker_state` | Canonical compact state snapshot |
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
| `get_trade_setup` | Compact agent-oriented trade setup for one ticker |

## Quickstart (local, stdio)

```bash
# Run straight from PyPI with uvx (or: pipx run tv-mcp)
uvx tv-mcp                       # stdio; uses TV_API_KEY or a config file

# …or from source
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp config.example.json config.json   # add your API key (git-ignored)
python -m tv_mcp                      # stdio by default
```

Validate:

```bash
ruff check . && pytest
```

### Credentials & precedence

The key is resolved in this order (first match wins):

1. **Per-request header** — `Authorization: Bearer <key>` (or `X-Api-Key`) — hosted mode.
2. **Environment** — `TV_API_KEY`.
3. **Local JSON config** — `tv_api_key` in `config.json` (see `config.example.json`; values
   support `${ENV_VAR}` substitution so the key can stay in the environment).
4. **Demo mode** — no key; only the demo tickers are available.

The key is never logged or persisted.

## Remote (hosted, HTTP + SSE)

```bash
TV_MCP_TRANSPORT=http PORT=8000 python -m tv_mcp   # serves http://0.0.0.0:8000/mcp
```

Each request carries its own key, so one deployment serves many users:

```
POST /mcp           Authorization: Bearer <your-key>
GET  /health        liveness probe
GET  /AGENTS.md      agent-discovery doc (how to use this server)
```

Container build (binds `$PORT`, runs the HTTP transport — deploys to any container host such
as Cloud Run, Fly, or ECS):

```bash
docker build -t tv-mcp .
docker run -p 8080:8080 tv-mcp
```

The server is stateless and holds no secrets, so it scales horizontally with no extra setup;
tune limits with the env vars in [`.env.example`](.env.example).

## Connecting an agent

**Claude Code / Claude Desktop (local, stdio)** — `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "trading-volatility": {
      "command": "uvx",
      "args": ["tv-mcp"],
      "env": { "TV_API_KEY": "your-key" }
    }
  }
}
```

**Remote MCP clients** (Claude web custom integrations, OpenAI Responses `mcp` tool, Gemini
function-calling, the Vercel AI SDK, ADK's `MCPToolset`, LangChain/LangGraph's
`MultiServerMCPClient`) all point at the same endpoint and pass the key as a header:

- **URL:** `https://<your-deployment>/mcp`
- **Header:** `Authorization: Bearer <your-key>`

Because the server is a standard streamable-HTTP MCP endpoint with header auth, no per-client
shim is needed — configure the URL and header in whichever framework you use. Copy-pasteable
guides with real code for each:

- [Anthropic Claude](docs/integrations/claude.md) — Claude Code, Desktop, the Messages API
  MCP connector, and Claude web
- [OpenAI](docs/integrations/openai.md) · [Google Gemini](docs/integrations/gemini.md) ·
  [Google ADK](docs/integrations/adk.md) ·
  [LangChain/LangGraph](docs/integrations/langchain.md) ·
  [Vercel AI SDK](docs/integrations/ai-sdk.md)
- Index: [docs/integrations/](docs/integrations/README.md)

## How it works

```
agent ──tools──▶  TV MCP  ──HTTPS (Bearer key)──▶  stocks.tradingvolatility.net/api/v2
                 (stateless)
```

The agent carries continuity between turns; the server keeps no session state. It forwards
the caller's key and returns the v2 payloads unchanged (they are already agent-shaped).

## Repository layout

```
src/tv_mcp/
  cli.py          stdio | http entry point
  server.py       FastMCP wiring (tools, resources, /health, /AGENTS.md)
  settings.py     config loading + precedence
  auth.py         credential resolution (header → env → config → demo)
  tv/             v2 API client + normalized errors
  tools/          one module per tool group (tickers, curves, discovery, auth)
  transports/     stateless HTTP + SSE app, per-request key middleware
tests/            client, auth, settings, tools, transport, smoke
docs/             design, build plan, implementation notes
```

## Docs

- [`docs/integrations/`](./docs/integrations/README.md) — per-framework integration guides
  (Claude, OpenAI, Gemini, ADK, LangChain, AI SDK)

> Deployment runbooks and maintainer planning artifacts are kept internal and excluded from
> public releases.

## License

MIT — see [LICENSE](./LICENSE). Open source under the Trading Volatility brand.
