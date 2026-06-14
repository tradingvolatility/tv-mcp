"""Tests for credential resolution and precedence."""

from __future__ import annotations

import json

import tv_mcp.auth as auth
from tv_mcp.auth import Credential, resolve_request_credential
from tv_mcp.settings import Settings


def test_demo_when_no_credential(clean_settings):
    cred = resolve_request_credential()
    assert cred.is_demo is True
    assert cred.api_key is None


def test_header_takes_precedence(clean_settings, with_api_key):
    cred = resolve_request_credential()
    assert cred.is_demo is False
    assert cred.api_key == "test-key-123"


def test_env_key_used_when_no_header(monkeypatch):
    test_settings = Settings(tv_api_key="env-key", tv_config_file=None)
    monkeypatch.setattr(auth, "get_settings", lambda: test_settings)
    cred = resolve_request_credential()
    assert cred.api_key == "env-key"


def test_config_file_used_when_no_header_or_env(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"tv_api_key": "file-key", "tv_api_base_url": "https://x/api/v2"}))
    test_settings = Settings(tv_api_key=None, tv_config_file=path)
    monkeypatch.setattr(auth, "get_settings", lambda: test_settings)
    cred = resolve_request_credential()
    assert cred.api_key == "file-key"
    assert cred.base_url == "https://x/api/v2"


def test_header_beats_env(monkeypatch, with_api_key):
    test_settings = Settings(tv_api_key="env-key", tv_config_file=None)
    monkeypatch.setattr(auth, "get_settings", lambda: test_settings)
    cred = resolve_request_credential()
    assert cred.api_key == "test-key-123"


def test_repr_masks_key():
    cred = Credential(api_key="super-secret", base_url="https://x")
    assert "super-secret" not in repr(cred)
    assert "***" in repr(cred)
