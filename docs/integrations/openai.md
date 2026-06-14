# OpenAI

The OpenAI **Responses API** can call a remote MCP server directly via an `mcp` tool — OpenAI
connects to your server, lists its tools, and calls them during the model's turn. This needs
the **remote (HTTP) deployment**; a local stdio process won't work here.

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5",  # use your current OpenAI model
    tools=[
        {
            "type": "mcp",
            "server_label": "trading_volatility",
            "server_url": "https://<your-deployment>/mcp",
            "headers": {"Authorization": "Bearer YOUR_TV_API_KEY"},
            "require_approval": "never",  # this server is read-only
        }
    ],
    input="What's AAPL's gamma regime, and what are the key levels?",
)

print(response.output_text)
```

Notes:

- `headers` is forwarded on every call to the MCP server — the TV server reads
  `Authorization: Bearer <key>`.
- `require_approval` defaults to prompting; set it to `"never"` here since every TV tool is
  read-only. You can also scope it per tool, e.g.
  `{"never": {"tool_names": ["get_ticker_state", "rank_top_setups"]}}`.
- Restrict the surfaced tools with `"allowed_tools": ["get_ticker_state", "rank_top_setups",
  "list_capabilities"]` on the tool object if you want a smaller set.
- The model's first call is typically `list_capabilities` to discover the available metrics
  and screeners.
