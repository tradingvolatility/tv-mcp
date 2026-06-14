# Anthropic Claude

Four ways to use the Trading Volatility MCP with Claude: **Claude Code** and **Claude
Desktop** (local stdio), the **Claude API MCP connector** (remote, from the Messages API),
and **Claude web custom integrations** (remote).

## Claude Code (local, stdio)

```bash
# Local: launches `uvx tv-mcp` over stdio, key from the environment
claude mcp add --env TV_API_KEY=$TV_API_KEY tv -- uvx tv-mcp
```

Or connect to a deployed remote server with header auth:

```bash
claude mcp add --transport http tv https://<your-deployment>/mcp \
  --header "Authorization: Bearer $TV_API_KEY"
```

Then ask Claude things like *"What's AAPL's gamma regime and key levels?"* — it will call
`get_ticker_state`, `get_levels`, etc.

## Claude Desktop (local, stdio)

Edit `claude_desktop_config.json` (Settings → Developer → Edit Config):

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

Restart Claude Desktop. The TV tools appear under the tools (🔌) menu.

## Claude API — MCP connector (remote)

The Messages API can call a remote MCP server directly via the `mcp_servers` parameter — no
client code, no local process. Requires the beta header `mcp-client-2025-11-20` (the SDK adds
it when you pass `betas=[...]`). The server must be reachable over HTTPS — point it at your
deployed endpoint.

```python
import anthropic

client = anthropic.Anthropic()

response = client.beta.messages.create(
    model="claude-opus-4-8",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Rank the top 5 trade setups right now."}],
    mcp_servers=[
        {
            "type": "url",
            "url": "https://<your-deployment>/mcp",
            "name": "trading-volatility",
            "authorization_token": "YOUR_TV_API_KEY",  # sent as Authorization: Bearer
        }
    ],
    tools=[{"type": "mcp_toolset", "mcp_server_name": "trading-volatility"}],
    betas=["mcp-client-2025-11-20"],
)
print(response)
```

The connector forwards `authorization_token` as the `Authorization: Bearer` header — exactly
what the TV server reads. Responses include `mcp_tool_use` / `mcp_tool_result` content blocks.

**Read-only safety, enforced at the connector.** This server is already read-only, but if you
want belt-and-suspenders you can allowlist just the tools you intend to use:

```python
tools=[{
    "type": "mcp_toolset",
    "mcp_server_name": "trading-volatility",
    "default_config": {"enabled": False},
    "configs": {
        "get_ticker_state": {"enabled": True},
        "rank_top_setups": {"enabled": True},
        "list_capabilities": {"enabled": True},
    },
}]
```

> Note: the MCP connector supports **tool calls** only (not MCP resources), so use the
> `list_capabilities` tool rather than the `tv://llm-spec` resource from the Messages API.

## Claude web — custom integration (remote)

In Claude (web/desktop) → Settings → Connectors → **Add custom connector**, enter your
deployed URL `https://<your-deployment>/mcp`. For header auth, deploy behind a gateway that
injects the `Authorization` header, or use the server's demo mode for the demo tickers.
See Anthropic's [custom integrations guide](https://support.anthropic.com/en/articles/11175166-getting-started-with-custom-integrations-using-remote-mcp).
