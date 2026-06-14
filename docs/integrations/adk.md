# Google ADK (Agent Development Kit)

ADK wraps an MCP server as an `MCPToolset` you hand to an `LlmAgent`. The toolset connects,
lists the TV tools, and exposes them to the agent.

```bash
pip install google-adk
```

## Remote (HTTP + SSE)

```python
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StreamableHTTPConnectionParams

tv_tools = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://<your-deployment>/mcp",
        headers={"Authorization": "Bearer YOUR_TV_API_KEY"},
    ),
)

agent = LlmAgent(
    model="gemini-2.5-pro",  # use your current model
    name="volatility_agent",
    instruction=(
        "You analyze options market structure with Trading Volatility data. "
        "Call list_capabilities first to see what's available, then answer the user."
    ),
    tools=[tv_tools],
)
```

Run `agent` with ADK's `Runner` as usual.

## Local (stdio)

```python
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioConnectionParams
from mcp import StdioServerParameters

tv_tools = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uvx", args=["tv-mcp"], env={"TV_API_KEY": "your-key"}
        ),
    ),
)
```

Notes:

- ADK's MCP connection-param class names track the `google-adk` version (e.g.
  `StreamableHTTPConnectionParams` / `SseConnectionParams` / `StdioConnectionParams`). If an
  import fails, check the [ADK MCP tools docs](https://google.github.io/adk-docs/tools/mcp-tools/)
  for your installed version.
- The `headers` dict is forwarded per request; the TV server reads `Authorization: Bearer`.
- Filter the tool surface with `tool_filter=["get_ticker_state", "rank_top_setups",
  "list_capabilities"]` on `MCPToolset` if you want a subset.
