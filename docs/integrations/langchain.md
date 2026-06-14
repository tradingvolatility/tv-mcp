# LangChain / LangGraph

`langchain-mcp-adapters` turns the TV MCP tools into LangChain tools you can hand to any
LangGraph agent. `MultiServerMCPClient` manages the connection.

```bash
pip install langchain-mcp-adapters langgraph "langchain[anthropic]"
```

## Remote (HTTP + SSE)

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

client = MultiServerMCPClient(
    {
        "trading_volatility": {
            "transport": "streamable_http",
            "url": "https://<your-deployment>/mcp",
            "headers": {"Authorization": "Bearer YOUR_TV_API_KEY"},
        }
    }
)


async def main():
    tools = await client.get_tools()
    agent = create_react_agent("anthropic:claude-opus-4-8", tools)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "What's AAPL's gamma regime?"}]}
    )
    print(result["messages"][-1].content)


asyncio.run(main())
```

## Local (stdio)

```python
client = MultiServerMCPClient(
    {
        "trading_volatility": {
            "transport": "stdio",
            "command": "uvx",
            "args": ["tv-mcp"],
            "env": {"TV_API_KEY": "your-key"},
        }
    }
)
```

Notes:

- `get_tools()` returns standard LangChain `StructuredTool`s — usable with `create_react_agent`,
  LCEL chains, or `bind_tools()` on a chat model.
- `headers` is forwarded per request; the TV server reads `Authorization: Bearer`. Omit it to
  use demo mode.
- The agent typically calls `list_capabilities` first to discover metrics and screeners.
