"""Shared test fixtures.

Tests never touch the network: ``respx_mock`` intercepts httpx, and an autouse fixture pins a
clean ``Settings`` (no env key, no config file) so demo mode and credential precedence are
deterministic regardless of the developer's environment.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

import tv_mcp.auth as auth
import tv_mcp.settings as settings_module
from tv_mcp.settings import DEFAULT_API_BASE_URL, Settings

BASE_URL = DEFAULT_API_BASE_URL


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Force a no-key, no-config-file Settings everywhere ``get_settings`` is called."""
    for var in ("TV_API_KEY", "TV_CONFIG_FILE", "TV_API_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    test_settings = Settings(tv_api_key=None, tv_config_file=None)
    monkeypatch.setattr(settings_module, "get_settings", lambda: test_settings)
    monkeypatch.setattr(auth, "get_settings", lambda: test_settings)
    yield test_settings


@pytest.fixture
def with_api_key() -> Iterator[str]:
    """Set a per-request API key (hosted-mode header path) for the duration of a test."""
    token = auth.current_request_api_key.set("test-key-123")
    try:
        yield "test-key-123"
    finally:
        auth.current_request_api_key.reset(token)
