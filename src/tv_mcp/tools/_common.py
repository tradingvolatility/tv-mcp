"""Shared helpers for Trading Volatility domain tools.

Every domain tool follows the same shape: resolve the credential, open a client, call the v2
API, and translate failures into a consistent, agent-readable error envelope rather than
raising — so the agent can decide what to tell the user.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from ..auth import resolve_request_credential
from ..settings import DEMO_TICKERS, get_settings
from ..tv.client import TVClient
from ..tv.errors import (
    TVAuthError,
    TVError,
    TVNotFoundError,
    TVRateLimitError,
)

logger = logging.getLogger("tv_mcp.tools")

# Allowed ticker characters: letters, digits, and the symbols real symbols use (e.g. BRK.B,
# ^VIX, ES=F). Deliberately excludes '/', whitespace, and '?#%' so caller input can never
# inject path segments, traverse with '..', or smuggle query params into the upstream URL.
_TICKER_RE = re.compile(r"^[A-Z0-9.^=\-]{1,16}$")


def normalize_ticker(ticker: str) -> str:
    """Uppercase and trim a ticker symbol (the v2 API expects uppercase)."""
    return ticker.strip().upper()


def is_valid_ticker(symbol: str) -> bool:
    """True if ``symbol`` (already normalized) is a syntactically valid ticker.

    A whitelist check at the tool boundary: input that fails here never reaches the URL path.
    """
    return bool(_TICKER_RE.fullmatch(symbol))


def error_envelope(reason: str, message: str, suggestion: str | None = None) -> dict[str, Any]:
    """Build a uniform error result."""
    error: dict[str, Any] = {"reason": reason, "message": message}
    if suggestion:
        error["suggestion"] = suggestion
    return {"error": error}


async def with_tv(
    handler: Callable[[TVClient], Awaitable[Any]],
    *,
    ticker: str | None = None,
) -> Any:
    """Run ``handler`` with an authenticated client, mapping failures to an error envelope.

    When the credential is demo (no key) and ``ticker`` is not a demo ticker, a 401 from the
    API is reported with a clear hint to add a key — that is the common first-run failure.

    When ``ticker`` is given it must be a syntactically valid symbol; invalid input is
    rejected here, before any request is built, so it can never reach the upstream URL path.
    """
    if ticker is not None and not is_valid_ticker(normalize_ticker(ticker)):
        return error_envelope(
            "invalid_input",
            f"{ticker!r} is not a valid ticker symbol.",
            "Use a plain symbol like AAPL, BRK.B, or ^VIX.",
        )

    credential = resolve_request_credential()

    # Public deployments can require a key: reject anonymous demo calls before any upstream
    # request, closing the "free anonymous proxy" path.
    if credential.is_demo and get_settings().tv_require_key:
        return error_envelope(
            "missing_credentials",
            "This server requires a Trading Volatility API key.",
            "Send your key as an Authorization: Bearer <key> header.",
        )

    demo_nonsupported = (
        credential.is_demo
        and ticker is not None
        and normalize_ticker(ticker) not in DEMO_TICKERS
    )

    try:
        async with credential.client() as client:
            result = await handler(client)
    except TVAuthError as exc:
        if demo_nonsupported:
            logger.info("tool call failed: reason=demo_ticker_required")
            return error_envelope(
                "missing_credentials",
                "No API key provided, and demo mode only covers the demo tickers "
                f"({', '.join(sorted(DEMO_TICKERS))}).",
                "Add your Trading Volatility API key to config.json or send it as an "
                "Authorization: Bearer <key> header, or query one of the demo tickers.",
            )
        reason = "insufficient_permissions" if exc.status_code == 403 else "invalid_credentials"
        logger.warning("tool call failed: reason=%s status=%s", reason, exc.status_code)
        return error_envelope(reason, "Trading Volatility rejected the credential.")
    except TVNotFoundError as exc:
        logger.info("tool call failed: reason=not_found")
        return error_envelope("not_found", str(exc))
    except TVRateLimitError:
        logger.warning("tool call failed: reason=rate_limited")
        return error_envelope(
            "rate_limited",
            "Trading Volatility is rate limiting requests.",
            "Wait a few seconds and try again.",
        )
    except TVError as exc:
        logger.warning("tool call failed: reason=error detail=%s", type(exc).__name__)
        envelope = error_envelope("error", str(exc))
        # Surface the API's own response detail (e.g. 4xx validation messages) so the
        # agent/user can see why a request was rejected. This is the caller's data, not a secret.
        detail = getattr(exc, "body_snippet", None)
        if detail:
            envelope["error"]["detail"] = detail
        return envelope
    except Exception:
        # Backstop: a tool must always return an envelope, never raise. Log the type for
        # diagnosis but keep internals out of the client-facing message.
        logger.exception("tool call failed: reason=unexpected")
        return error_envelope("error", "An unexpected error occurred handling the request.")

    # Success. A success with no body (204/304/empty) comes back as None; coerce it to an
    # empty object so the structured (dict) tool result is always well-formed.
    return {} if result is None else result
