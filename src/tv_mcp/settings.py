"""Configuration for the Trading Volatility MCP server (T0.3).

Two layers, matching the two deployment modes:

- ``Settings`` — server-level config from environment / ``.env`` (base URL, log level, bind
  address, transport, and the path to a local JSON config). Applies to both modes.
- ``LocalConfig`` — the local-mode JSON config file holding single-user credentials. In
  hosted mode this is absent and the API key arrives per request via the ``Authorization``
  (or ``X-Api-Key``) header (resolved in ``auth.py``, not here).

**Credential precedence** (highest first), implemented in ``auth.resolve_request_credential``:

  1. per-request header (``Authorization: Bearer <key>`` or ``X-Api-Key``) — hosted mode
  2. ``TV_API_KEY`` environment variable
  3. ``tv_api_key`` in the local JSON config file
  4. demo mode (no key) — works for the demo tickers only

The server never persists credentials; this module only loads configuration.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# Matches ${VAR} references in config values for environment-variable substitution.
_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

DEFAULT_API_BASE_URL = "https://stocks.tradingvolatility.net/api/v2"

# Auth headers the v2 API accepts (api/api_auth.py::require_legacy_access). We forward the
# caller's key as a Bearer token by default; X-Api-Key is also read inbound (hosted mode).
AUTH_HEADER = "Authorization"
API_KEY_HEADER = "X-Api-Key"
# Demo passthrough: set on requests with no key so the v2 API serves the demo tickers.
DEMO_HEADER = "X-TV-Demo"
# Tickers the v2 API serves in demo mode without a key (confirmed from the v2 docs).
DEMO_TICKERS = frozenset({"AAPL", "VIX", "KO", "META", "AMZN", "XOM", "GM", "MCD"})


class Settings(BaseSettings):
    """Server-level configuration, read from environment variables / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    tv_api_base_url: str = DEFAULT_API_BASE_URL
    # Optional path to a local-mode JSON config. Unset/None in hosted mode.
    tv_config_file: Path | None = None
    # Optional API key straight from the environment (precedence above the config file).
    tv_api_key: str | None = None
    log_level: str = "INFO"
    # Transport for `python -m tv_mcp` / `tv-mcp` when not overridden on the CLI.
    tv_mcp_transport: str = "stdio"
    # Bind address for the HTTP transport. Default to localhost for local dev; containers set
    # HOST=0.0.0.0 and PORT (e.g. Cloud Run injects PORT) — both read case-insensitively.
    host: str = "127.0.0.1"
    port: int = 8000
    # Comma-separated CORS allow-origins for the HTTP transport. "*" allows any origin (the
    # default — the server holds no cookies/session and auth is per-request header).
    cors_allow_origins: str = "*"
    # Max inbound request body in bytes for the HTTP transport (MCP JSON-RPC is tiny). Oversized
    # requests are rejected with 413 before buffering, to bound memory under load.
    tv_max_request_bytes: int = 262144
    # Reject anonymous demo-mode calls (no key) before any upstream request. Default off to keep
    # demo working out of the box; set true on public deployments to stop anonymous proxying.
    tv_require_key: bool = False
    # Upstream retry budget per call. Lower it (e.g. 1) in hosted mode so one inbound request
    # can't fan out and sleep while holding a slot.
    tv_max_retries: int = 2
    # Upstream per-request timeout in seconds.
    tv_request_timeout: float = 30.0


class LocalConfig(BaseModel):
    """Schema for the local-mode JSON config file (see config.example.json)."""

    tv_api_key: str = Field(..., min_length=1)
    tv_api_base_url: str = DEFAULT_API_BASE_URL


class ConfigError(Exception):
    """Raised when a local config file exists but cannot be read or is invalid."""


def _expand_env_vars(value: Any) -> Any:
    """Recursively substitute ``${VAR}`` references in config strings with env values.

    Keeps secrets out of the file: a config can hold ``"${TV_API_KEY}"`` and the real key
    lives in the environment. Raises ``ConfigError`` if a referenced variable is unset.
    """
    if isinstance(value, str):

        def _replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in os.environ:
                raise ConfigError(
                    f"Config references ${{{name}}} but environment variable {name} is not set."
                )
            return os.environ[name]

        return _ENV_VAR_RE.sub(_replace, value)
    if isinstance(value, dict):
        return {key: _expand_env_vars(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


def load_local_config(path: str | Path | None) -> LocalConfig | None:
    """Load and validate the local-mode JSON config.

    Returns ``None`` when ``path`` is falsy or the file does not exist (hosted mode, or local
    mode without a config yet). ``${VAR}`` placeholders in values are expanded from the
    environment. Raises ``ConfigError`` when the file exists but is malformed, references an
    unset variable, or fails validation — a present-but-broken config is a real error, not a
    silent fallback.
    """
    if not path:
        return None
    config_path = Path(path)
    if not config_path.exists():
        return None
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Could not read config file {config_path}: {exc}") from exc
    raw = _expand_env_vars(raw)
    try:
        return LocalConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"Invalid config file {config_path}: {exc}") from exc


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide server settings (cached)."""
    return Settings()
