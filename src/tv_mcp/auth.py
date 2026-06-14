"""Credential resolution.

Resolves the Trading Volatility account context for a call, in precedence order:

  1. **Hosted mode** — a per-request ``Authorization: Bearer <key>`` (or ``X-Api-Key``)
     header, captured by the transport middleware into ``current_request_api_key``.
  2. **Environment** — ``TV_API_KEY``.
  3. **Local mode** — ``tv_api_key`` from the local JSON config file.
  4. **Demo mode** — no key. The client then sends ``X-TV-Demo: 1`` and the v2 API serves
     the demo tickers only.

This module decides *which* credential to use; it does not validate it. Validity (invalid vs.
insufficient-permission) is determined when the key is used against the API (``TVAuthError``
401 vs 403). The credential is never logged: ``Credential.__repr__`` masks the key.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from .settings import Settings, get_settings, load_local_config
from .tv.client import TVClient, get_pooled_client

# Per-request API key for hosted mode. Set by the transport middleware from the
# Authorization / X-Api-Key header and reset after each request, so no credential persists or
# leaks across requests. None in local/demo mode.
current_request_api_key: ContextVar[str | None] = ContextVar(
    "current_request_api_key", default=None
)


@dataclass(frozen=True)
class Credential:
    """A resolved credential scoped to one account for the duration of a call.

    ``api_key`` is ``None`` in demo mode — a valid state, not an error, so the demo tickers
    work out of the box without a subscription.
    """

    api_key: str | None
    base_url: str
    max_retries: int = 2
    timeout: float = 30.0

    @property
    def is_demo(self) -> bool:
        return not self.api_key

    def __repr__(self) -> str:  # never expose the key in logs/tracebacks
        shown = "***" if self.api_key else None
        return f"Credential(api_key={shown!r}, base_url={self.base_url!r}, demo={self.is_demo})"

    def client(self) -> TVClient:
        # Reuse the process-wide pooled client when enabled (hosted HTTP mode); otherwise the
        # TVClient owns a per-call client. Auth is sent per request either way.
        return TVClient(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
            client=get_pooled_client(self.base_url, timeout=self.timeout),
        )


def resolve_request_credential(settings: Settings | None = None) -> Credential:
    """Resolve the credential for the current request, following the documented precedence.

    Never raises for a missing key: with no key from any source it returns a demo credential,
    so demo-ticker calls succeed and only non-demo calls hit the API's auth wall.
    """
    settings = settings or get_settings()
    common = {"max_retries": settings.tv_max_retries, "timeout": settings.tv_request_timeout}

    header_key = current_request_api_key.get()
    if header_key:
        return Credential(api_key=header_key, base_url=settings.tv_api_base_url, **common)

    if settings.tv_api_key:
        return Credential(api_key=settings.tv_api_key, base_url=settings.tv_api_base_url, **common)

    config = load_local_config(settings.tv_config_file)
    if config:
        return Credential(api_key=config.tv_api_key, base_url=config.tv_api_base_url, **common)

    return Credential(api_key=None, base_url=settings.tv_api_base_url, **common)
