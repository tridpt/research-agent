"""Security and formatting tests for UI-only helper functions."""
from __future__ import annotations

from ui.helpers import parse_model_list, report_to_html, secret_default


def test_report_to_html_strips_active_html_and_unsafe_urls() -> None:
    output = report_to_html(
        "Safe title",
        "# Heading\n\n**bold** <img src=x onerror=alert(1)> <script>alert(1)</script> "
        "[bad](javascript:alert(1))",
    )
    lowered = output.lower()

    assert "<h1>heading</h1>" in lowered
    assert "<strong>bold</strong>" in lowered
    assert "<script" not in lowered
    assert "onerror" not in lowered
    assert "javascript:" not in lowered
    assert "cdn.jsdelivr" not in lowered


def test_parse_model_list_dedupes_trims_and_caps() -> None:
    models = parse_model_list("gpt-4o-mini, gpt-4o-mini ,\n llama-3.3-70b , , gemini, extra1, extra2")
    assert models == ["gpt-4o-mini", "llama-3.3-70b", "gemini", "extra1"]


def test_parse_model_list_empty() -> None:
    assert parse_model_list("") == []
    assert parse_model_list("   ,  ") == []


def test_secret_default_prefers_secrets_then_env_then_default() -> None:
    secrets = {"RESEARCH_AGENT_API_KEY": "from-secrets"}
    env = {"RESEARCH_AGENT_API_KEY": "from-env"}
    assert secret_default(secrets, env, "RESEARCH_AGENT_API_KEY") == "from-secrets"


def test_secret_default_falls_back_to_env_when_secret_missing() -> None:
    assert secret_default({}, {"K": "e"}, "K") == "e"
    assert secret_default(None, {"K": "e"}, "K") == "e"


def test_secret_default_uses_default_when_nothing_set() -> None:
    assert secret_default(None, {}, "K", "fallback") == "fallback"
    assert secret_default({}, {}, "K") == ""


def test_secret_default_ignores_empty_secret_value() -> None:
    # An empty secret should not shadow a usable env value.
    assert secret_default({"K": ""}, {"K": "e"}, "K") == "e"


def test_secret_default_survives_secrets_access_errors() -> None:
    class _Raising:
        def __contains__(self, key):
            raise FileNotFoundError("no secrets file")

    assert secret_default(_Raising(), {"K": "e"}, "K") == "e"
