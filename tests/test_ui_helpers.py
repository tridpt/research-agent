"""Security and formatting tests for UI-only helper functions."""
from __future__ import annotations

from ui.helpers import parse_model_list, report_to_html


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
