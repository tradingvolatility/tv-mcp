"""Normalized Trading Volatility API errors.

These wrap transport- and HTTP-level failures into a small, predictable hierarchy that tools
translate into agent-readable responses. Error messages never include the API key or request
headers.
"""

from __future__ import annotations


class TVError(Exception):
    """Base class for all Trading Volatility client errors."""


class TVConnectionError(TVError):
    """The request never produced an HTTP response (timeout, DNS, connection refused)."""


class TVAPIError(TVError):
    """The API returned a non-2xx response."""

    def __init__(self, status_code: int, message: str, *, body_snippet: str | None = None):
        self.status_code = status_code
        self.body_snippet = body_snippet
        super().__init__(message)


class TVAuthError(TVAPIError):
    """401 / 403 — missing, invalid, or insufficient credentials."""


class TVNotFoundError(TVAPIError):
    """404 — the ticker/resource does not exist or is not visible to this account."""


class TVRateLimitError(TVAPIError):
    """429 — too many requests; back off and retry."""


class TVRequestError(TVAPIError):
    """Other 4xx — the request was rejected (bad input, conflict, etc.)."""


class TVServerError(TVAPIError):
    """5xx — Trading Volatility-side failure."""
