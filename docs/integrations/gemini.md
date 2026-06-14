# Google Gemini

The Google **GenAI SDK** (`google-genai`) has built-in MCP support: pass an MCP
`ClientSession` directly in `config.tools` and the SDK handles tool discovery and calling
(automatic function calling). You manage the MCP connection with the standard `mcp` client
library.

```bash
pip install google-genai mcp
```

## Remote (HTTP + SSE)

```python
import asyncio
from google import genai
from google.genai import types
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

client = genai.Client()  # GEMINI_API_KEY from the environment
TV_URL = "https://<your-deployment>/mcp"
HEADERS = {"Authorization": "Bearer YOUR_TV_API_KEY"}


async def main():
    async with streamablehttp_client(TV_URL, headers=HEADERS) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await client.aio.models.generate_content(
                model="gemini-2.5-pro",  # use your current Gemini model
                contents="What are the top 5 trade setups right now?",
                config=types.GenerateContentConfig(
                    tools=[session],  # the SDK exposes the MCP tools automatically
                ),
            )
            print(response.text)


asyncio.run(main())
```

## Local (stdio)

Swap the transport to launch `uvx tv-mcp` as a subprocess; everything else is identical:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

params = StdioServerParameters(command="uvx", args=["tv-mcp"], env={"TV_API_KEY": "your-key"})
async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        # ... same generate_content call as above, tools=[session]
```

Notes:

- The TV server reads `Authorization: Bearer <key>` from the headers you pass to
  `streamablehttp_client`. With no key, the demo tickers still work.
- Automatic function calling runs the tool round-trips for you; the model usually starts with
  `list_capabilities` to self-orient.
