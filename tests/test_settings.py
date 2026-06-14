"""Tests for config loading (T0.3)."""

from __future__ import annotations

import json

import pytest

from tv_mcp.settings import ConfigError, load_local_config


def test_load_missing_path_returns_none():
    assert load_local_config(None) is None
    assert load_local_config("/no/such/file.json") is None


def test_load_valid_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"tv_api_key": "abc", "tv_api_base_url": "https://x/api/v2"}))
    config = load_local_config(path)
    assert config is not None
    assert config.tv_api_key == "abc"
    assert config.tv_api_base_url == "https://x/api/v2"


def test_env_var_substitution(tmp_path, monkeypatch):
    monkeypatch.setenv("TV_API_KEY", "from-env")
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"tv_api_key": "${TV_API_KEY}"}))
    config = load_local_config(path)
    assert config is not None
    assert config.tv_api_key == "from-env"


def test_env_var_missing_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("TV_API_KEY", raising=False)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"tv_api_key": "${TV_API_KEY}"}))
    with pytest.raises(ConfigError):
        load_local_config(path)


def test_invalid_json_raises(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json")
    with pytest.raises(ConfigError):
        load_local_config(path)


def test_missing_required_key_raises(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"tv_api_base_url": "https://x"}))
    with pytest.raises(ConfigError):
        load_local_config(path)
