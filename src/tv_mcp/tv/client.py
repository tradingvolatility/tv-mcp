"""Async client for the Trading Volatility v2 API (T0.4).

The only component that talks to Trading Volatility. Wraps httpx with the caller's API key as
an ``Authorization: Bearer`` header (or the ``X-TV-Demo`` header when no key is supplied, for
demo tickers), retries transient failures, normalizes errors (``errors.py``), and returns
parsed JSON. Holds no state beyond the configured credential; one instance is scoped to one
authenticated account for the duration of a request.

Every public method is a thin wrapper over one read-only GET endpoint — the MCP forwards
query parameters as-is and does not reshape responses (the v2 payloads are already
agent-shaped). ``304 Not Modified`` is treated as success with no body.
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

import httpx

from ..settings import AUTH_HEADER, DEFAULT_API_BASE_URL, DEMO_HEADER
from .errors import (
    TVAuthError,
    TVConnectionError,
    TVNotFoundError,
    TVRateLimitError,
    TVRequestError,
    TVServerError,
)

_DEFAULT_TIMEOUT = 30.0
_MAX_BODY_SNIPPET = 500
_DEFAULT_MAX_RETRIES = 2
_RETRY_STATUSES = {429, 502, 503, 504}


# --- Connection pooling (hosted HTTP mode) ----------------------------------------------
#
# By default each call uses its own AsyncClient (simple, correct for stdio/local). In the
# hosted HTTP path we enable one process-wide client per base_url so we don't pay a fresh
# TCP+TLS handshake per request (a latency cost and a DoS amplifier under load). Auth is sent
# per request, so the shared client never holds a credential.
_pool_enabled = False
_pooled_clients: dict[str, httpx.AsyncClient] = {}


def enable_connection_pool() -> None:
    """Use one shared AsyncClient per base_url for subsequent calls (call once at HTTP startup)."""
    global _pool_enabled
    _pool_enabled = True


def get_pooled_client(
    base_url: str, *, timeout: float = _DEFAULT_TIMEOUT
) -> httpx.AsyncClient | None:
    """Return the shared client for ``base_url`` (creating it lazily), or None if disabled."""
    if not _pool_enabled:
        return None
    key = base_url.rstrip("/")
    existing = _pooled_clients.get(key)
    if existing is None:
        existing = httpx.AsyncClient(base_url=key, timeout=timeout)
        _pooled_clients[key] = existing
    return existing


async def aclose_pooled_clients() -> None:
    """Close and forget all pooled clients (shutdown / test teardown)."""
    global _pooled_clients
    clients, _pooled_clients = list(_pooled_clients.values()), {}
    for client in clients:
        await client.aclose()


def _seg(value: str) -> str:
    """Percent-encode a value for safe use as a single URL path segment.

    Defense in depth: tools already whitelist tickers/screener names, but encoding here means
    that even if an unvalidated value reaches the client it cannot inject a '/', traverse with
    '..', or open a query string in the upstream request.
    """
    return quote(value, safe="")


class TVClient:
    """Thin async wrapper over the Trading Volatility v2 API.

    Pass ``api_key`` to authenticate, or leave it ``None`` to use demo mode (the server then
    sends ``X-TV-Demo: 1`` and the API serves the demo tickers only).

    Usage::

        async with TVClient(api_key=key) as client:
            state = await client.get_ticker_state("AAPL")
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_API_BASE_URL,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        retry_backoff: float = 0.5,
        client: httpx.AsyncClient | None = None,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._owns_client = client is None
        # Auth is supplied per request in ``_get`` (never as a client default header), so the
        # underlying AsyncClient carries no credential. That is what makes a shared/pooled
        # client safe across callers — one client, a different key on each request.
        self._client = client or httpx.AsyncClient(base_url=self._base_url, timeout=timeout)

    @property
    def is_demo(self) -> bool:
        return not self._api_key

    def _auth_headers(self) -> dict[str, str]:
        """Build the auth headers for every request from the configured credential."""
        if self._api_key:
            return {AUTH_HEADER: f"Bearer {self._api_key}"}
        # No key → demo mode. The v2 API gates demo access on this header.
        return {DEMO_HEADER: "1"}

    async def __aenter__(self) -> TVClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """GET ``path`` and return parsed JSON, raising a normalized error on failure.

        Transient failures (timeouts, transport errors, 429/5xx) are retried with backoff.
        Query params that are ``None`` are dropped so we never send empty values.
        """
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        headers = self._auth_headers()
        attempt = 0
        while True:
            try:
                response = await self._client.get(path, params=clean_params, headers=headers)
            except (httpx.TimeoutException, httpx.HTTPError) as exc:
                if attempt < self._max_retries:
                    attempt += 1
                    await self._backoff(attempt)
                    continue
                raise TVConnectionError(
                    f"Could not reach Trading Volatility: GET {path}"
                ) from exc

            # 304 (conditional cache hit) has no body; treat as success.
            if response.is_success or response.status_code == 304:
                if response.status_code in (204, 304) or not response.content:
                    return None
                try:
                    return response.json()
                except ValueError as exc:
                    # A success status with a non-JSON body (e.g. a CDN/WAF challenge or
                    # gateway page sitting in front of the API). Treat as an upstream failure
                    # rather than letting the JSON decode error escape unmapped.
                    snippet = response.text[:_MAX_BODY_SNIPPET] if response.text else None
                    raise TVServerError(
                        response.status_code,
                        "Trading Volatility returned a non-JSON "
                        f"{response.status_code} body for "
                        f"{response.request.method} {response.request.url.path}",
                        body_snippet=snippet,
                    ) from exc

            if response.status_code in _RETRY_STATUSES and attempt < self._max_retries:
                attempt += 1
                await self._backoff(attempt, response)
                continue

            self._raise_for_status(response)

    async def _backoff(self, attempt: int, response: httpx.Response | None = None) -> None:
        delay = self._retry_backoff * (2 ** (attempt - 1))
        if response is not None:
            retry_after = response.headers.get("retry-after", "")
            if retry_after.isdigit():
                delay = float(retry_after)
        if delay > 0:
            await asyncio.sleep(delay)

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        status = response.status_code
        snippet = response.text[:_MAX_BODY_SNIPPET] if response.text else None
        req = response.request
        base = f"Trading Volatility API returned {status} for {req.method} {req.url.path}"
        if status in (401, 403):
            raise TVAuthError(status, f"{base}: authentication failed", body_snippet=snippet)
        if status == 404:
            raise TVNotFoundError(status, f"{base}: not found", body_snippet=snippet)
        if status == 429:
            raise TVRateLimitError(status, f"{base}: rate limited", body_snippet=snippet)
        if 400 <= status < 500:
            raise TVRequestError(status, f"{base}: request rejected", body_snippet=snippet)
        raise TVServerError(status, f"{base}: server error", body_snippet=snippet)

    # --- Ticker state (T1.1) ---------------------------------------------------

    async def get_ticker_state(self, ticker: str, *, include: str | None = None) -> Any:
        """``GET /tickers/{ticker}`` — canonical compact state snapshot."""
        return await self._get(f"/tickers/{_seg(ticker)}", params={"include": include})

    async def explain_ticker(self, ticker: str, *, view: str | None = None) -> Any:
        """``GET /tickers/{ticker}/explain`` — deterministic regime interpretation."""
        return await self._get(f"/tickers/{_seg(ticker)}/explain", params={"view": view})

    async def get_market_structure(self, ticker: str, *, include: str | None = None) -> Any:
        """``GET /tickers/{ticker}/market-structure`` — assembled market-structure read."""
        return await self._get(
            f"/tickers/{_seg(ticker)}/market-structure", params={"include": include}
        )

    async def get_signals(self, ticker: str) -> Any:
        """``GET /tickers/{ticker}/signals`` — current signals."""
        return await self._get(f"/tickers/{_seg(ticker)}/signals")

    async def get_levels(self, ticker: str, *, view: str | None = None) -> Any:
        """``GET /tickers/{ticker}/levels`` — key levels (json | tradingview | tos)."""
        return await self._get(f"/tickers/{_seg(ticker)}/levels", params={"view": view})

    # --- Curves / series (T1.2) ------------------------------------------------

    async def get_series(
        self, ticker: str, *, metrics: str | None = None, window: str | None = None
    ) -> Any:
        """``GET /tickers/{ticker}/series`` — historical time series for selected metrics."""
        return await self._get(
            f"/tickers/{_seg(ticker)}/series", params={"metrics": metrics, "window": window}
        )

    async def get_gamma_curve(
        self, ticker: str, *, exp: str | None = None, realtime: bool | None = None
    ) -> Any:
        """``GET /tickers/{ticker}/curves/gamma`` — gamma strike curve (net gamma/strike)."""
        return await self._get(
            f"/tickers/{_seg(ticker)}/curves/gamma", params={"exp": exp, "realtime": realtime}
        )

    async def get_gamma_by_expiration(self, ticker: str) -> Any:
        """``GET /tickers/{ticker}/curves/gamma/expirations`` — gamma by expiration bucket."""
        return await self._get(f"/tickers/{_seg(ticker)}/curves/gamma/expirations")

    async def get_gex_by_strike(self, ticker: str, *, exp: str | None = None) -> Any:
        """``GET /tickers/{ticker}/curves/gex_by_strike`` — net GEX strike curve."""
        return await self._get(f"/tickers/{_seg(ticker)}/curves/gex_by_strike", params={"exp": exp})

    async def get_options_volume(
        self, ticker: str, *, exp: str, include: str | None = None
    ) -> Any:
        """``GET /tickers/{ticker}/options/volume`` — options volume by strike (exp required)."""
        return await self._get(
            f"/tickers/{_seg(ticker)}/options/volume", params={"exp": exp, "include": include}
        )

    # --- Discovery / ranking (T1.3) --------------------------------------------

    async def get_top_setups(self, params: dict[str, Any] | None = None) -> Any:
        """``GET /top-setups`` — cross-ticker ranking by opportunity score, with filters."""
        return await self._get("/top-setups", params=params)

    async def run_screener(self, name: str, params: dict[str, Any] | None = None) -> Any:
        """``GET /top-setups/screener/{name}`` — a named preset over the same ranking."""
        return await self._get(f"/top-setups/screener/{_seg(name)}", params=params)

    async def get_trade_setup(self, ticker: str) -> Any:
        """``GET /agent/trade-setup/{ticker}`` — compact agent-oriented trade setup."""
        return await self._get(f"/agent/trade-setup/{_seg(ticker)}")

    # --- Capabilities / discovery helper (T1.4) --------------------------------

    async def get_llm_spec(self) -> Any:
        """``GET /llm-spec`` — the machine-readable capability manifest for agents."""
        return await self._get("/llm-spec")
