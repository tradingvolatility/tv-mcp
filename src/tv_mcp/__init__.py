"""Trading Volatility MCP — a Model Context Protocol server for Trading Volatility.

Exposes the public v2 options/volatility API (state snapshots, signals, market structure,
levels, time series, gamma/GEX curves, options volume, and ranked trade setups) as
agent-usable tools. Read-only: the server discovers and retrieves data — it never places
orders or takes payments. It is a stateless passthrough that forwards the caller's API key
to the v2 API and stores nothing.
"""

__version__ = "0.1.0"
