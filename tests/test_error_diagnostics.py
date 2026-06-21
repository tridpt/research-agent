"""Regression tests for safe, actionable LLM error messages."""
from __future__ import annotations

import pytest

from research_agent.error_diagnostics import diagnose_llm_error
from research_agent.errors import LLMError


@pytest.mark.parametrize(
    ("message", "kind", "retryable"),
    [
        ("LLM HTTP 401: invalid_api_key", "authentication", False),
        ("LLM HTTP 429: quota exceeded", "rate_limit", True),
        ("LLM request timed out: network issue", "network", True),
        ("LLM HTTP 503: service unavailable", "provider_unavailable", True),
        ("LLM HTTP 404: model_not_found", "model_not_found", False),
        ("LLM HTTP 400: tool call validation failed", "tool_call", False),
        ("LLM HTTP 400: invalid request", "invalid_request", False),
    ],
)
def test_diagnose_llm_error_is_actionable(message: str, kind: str, retryable: bool) -> None:
    diagnosis = diagnose_llm_error(LLMError(message))

    assert diagnosis.kind == kind
    assert diagnosis.retryable is retryable
    assert diagnosis.title_vi
    assert diagnosis.detail_vi
    assert diagnosis.suggestions_vi


def test_diagnosis_never_echoes_provider_response_or_secrets() -> None:
    diagnosis = diagnose_llm_error("LLM HTTP 400: api_key=super-secret-value")
    rendered = " ".join((diagnosis.title_vi, diagnosis.detail_vi, *diagnosis.suggestions_vi))

    assert "super-secret-value" not in rendered
