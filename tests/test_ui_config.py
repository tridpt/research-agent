"""Unit tests for the pure UI config/policy helpers extracted from app.py."""
from __future__ import annotations

from pathlib import Path

import pytest
from ui.config_ui import (
    DEFAULT_ALLOWED_LLM_HOSTS,
    PRESETS,
    load_env_file,
    parse_allowed_hosts,
    validated_llm_base_url,
)

from research_agent.errors import ConfigError


def test_load_env_file_parses_pairs_and_skips_comments(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# a comment\n\nKEY=value\n  SPACED = trimmed \nNOEQUALS\n",
        encoding="utf-8",
    )
    assert load_env_file(env) == {"KEY": "value", "SPACED": "trimmed"}


def test_load_env_file_missing_returns_empty(tmp_path: Path) -> None:
    assert load_env_file(tmp_path / "nope.env") == {}


def test_parse_allowed_hosts_merges_defaults_and_extras() -> None:
    hosts = parse_allowed_hosts("llm.example.com, Other.Example.COM. ,")
    assert DEFAULT_ALLOWED_LLM_HOSTS <= hosts
    assert "llm.example.com" in hosts
    assert "other.example.com" in hosts  # lowercased, trailing dot stripped


def test_parse_allowed_hosts_empty_is_just_defaults() -> None:
    assert parse_allowed_hosts("") == DEFAULT_ALLOWED_LLM_HOSTS


def test_validated_llm_base_url_accepts_allowed_https_host() -> None:
    allowed = parse_allowed_hosts("")
    assert validated_llm_base_url("https://api.groq.com/openai/v1/", allowed) == (
        "https://api.groq.com/openai/v1"
    )


def test_validated_llm_base_url_rejects_http() -> None:
    with pytest.raises(ConfigError, match="HTTPS"):
        validated_llm_base_url("http://api.groq.com/v1", parse_allowed_hosts(""))


def test_validated_llm_base_url_rejects_unlisted_host() -> None:
    with pytest.raises(ConfigError, match="chưa được cho phép"):
        validated_llm_base_url("https://evil.example.com/v1", parse_allowed_hosts(""))


def test_validated_llm_base_url_rejects_embedded_credentials() -> None:
    allowed = parse_allowed_hosts("")
    with pytest.raises(ConfigError, match="credentials"):
        validated_llm_base_url("https://user:pass@api.groq.com/v1", allowed)


def test_validated_llm_base_url_rejects_query_and_fragment() -> None:
    allowed = parse_allowed_hosts("")
    with pytest.raises(ConfigError, match="query"):
        validated_llm_base_url("https://api.groq.com/v1?x=1", allowed)


def test_validated_llm_base_url_allows_custom_host_when_configured() -> None:
    allowed = parse_allowed_hosts("llm.example.com")
    assert validated_llm_base_url("https://llm.example.com:8443/v1", allowed) == (
        "https://llm.example.com:8443/v1"
    )


def test_presets_expose_known_providers() -> None:
    assert set(PRESETS) >= {"Groq", "Gemini", "OpenAI"}
    assert PRESETS["Groq"][0].startswith("https://")
