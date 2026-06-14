# Vercel AI SDK

The AI SDK's MCP client (`experimental_createMCPClient`) discovers the TV tools and exposes
them to `generateText` / `streamText`.

```bash
npm install ai @modelcontextprotocol/sdk @ai-sdk/anthropic
```

## Remote (HTTP + SSE)

```ts
import { experimental_createMCPClient as createMCPClient, generateText } from "ai";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { anthropic } from "@ai-sdk/anthropic";

const mcpClient = await createMCPClient({
  transport: new StreamableHTTPClientTransport(new URL("https://<your-deployment>/mcp"), {
    requestInit: {
      headers: { Authorization: `Bearer ${process.env.TV_API_KEY}` },
    },
  }),
});

try {
  const tools = await mcpClient.tools();
  const { text } = await generateText({
    model: anthropic("claude-opus-4-8"), // use your provider/model of choice
    tools,
    maxSteps: 5, // allow tool round-trips
    prompt: "Rank the top 5 trade setups right now.",
  });
  console.log(text);
} finally {
  await mcpClient.close();
}
```

## Local (stdio)

```ts
import { experimental_createMCPClient as createMCPClient } from "ai";
import { Experimental_StdioMCPTransport as StdioMCPTransport } from "ai/mcp-stdio";

const mcpClient = await createMCPClient({
  transport: new StdioMCPTransport({
    command: "uvx",
    args: ["tv-mcp"],
    env: { TV_API_KEY: process.env.TV_API_KEY! },
  }),
});
// ... same mcpClient.tools() + generateText as above
```

Notes:

- The `Authorization: Bearer` header is forwarded per request; the TV server reads it. Omit it
  for demo mode.
- `maxSteps > 1` lets the model call a tool, read the result, and continue — needed for
  multi-step flows like "discover with `list_capabilities`, then query a ticker".
- Always `close()` the client when done to release the connection.
