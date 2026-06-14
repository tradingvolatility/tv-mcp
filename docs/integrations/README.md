# Integration guides

How to connect the Trading Volatility MCP server to the major agent frameworks and LLM
providers. Every guide uses the **same two deployment shapes**:

- **Local (stdio)** — the agent launches `uvx tv-mcp` as a subprocess. Credentials come from
  `TV_API_KEY` (or a local `config.json`).
- **Remote (HTTP + SSE)** — the agent connects to your deployed `https://<host>/mcp` endpoint
  and sends the key as an `Authorization: Bearer <key>` header per request.

Without a key, the demo tickers (AAPL, VIX, KO, META, AMZN, XOM, GM, MCD) work everywhere.

| Guide | Framework / provider | Transport shown |
|-------|----------------------|-----------------|
| [claude.md](./claude.md) | Anthropic — Claude Code, Claude Desktop, Claude API MCP connector, Claude web | stdio + remote |
| [openai.md](./openai.md) | OpenAI — Responses API remote MCP tool | remote |
| [gemini.md](./gemini.md) | Google Gemini — GenAI SDK MCP function calling | remote (+ stdio) |
| [adk.md](./adk.md) | Google ADK — `MCPToolset` | remote (+ stdio) |
| [langchain.md](./langchain.md) | LangChain / LangGraph — `langchain-mcp-adapters` | remote (+ stdio) |
| [ai-sdk.md](./ai-sdk.md) | Vercel AI SDK — `experimental_createMCPClient` | remote (+ stdio) |

> Replace `https://<your-deployment>/mcp` with your deployed URL, and `$TV_API_KEY` with a
> real Trading Volatility key. The endpoint is a standard streamable-HTTP MCP server with
> header auth, so any MCP-capable client not listed here works the same way: point it at the
> URL and pass the `Authorization: Bearer` header.

A good first call from any client is `list_capabilities` (the v2 `/llm-spec` manifest) so the
agent can self-orient before querying tickers.
