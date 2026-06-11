"""Tests for token usage tracking and cost estimation."""
from __future__ import annotations

from research_agent.usage import (
    UsageTracker,
    estimate_cost,
    format_usage,
)


def test_tracker_accumulates() -> None:
    t = UsageTracker()
    t.record({"prompt_tokens": 100, "completion_tokens": 20})
    t.record({"prompt_tokens": 50, "completion_tokens": 10})
    assert t.calls == 2
    assert t.prompt_tokens == 150
    assert t.completion_tokens == 30
    assert t.total_tokens == 180


def test_tracker_handles_missing_usage() -> None:
    t = UsageTracker()
    t.record(None)
    t.record({})
    assert t.calls == 2
    assert t.total_tokens == 0


def test_estimate_cost_known_model() -> None:
    # gpt-4o-mini: 0.15 / 0.60 per 1M
    cost = estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost is not None
    assert abs(cost - (0.15 + 0.60)) < 1e-9


def test_estimate_cost_free_model() -> None:
    assert estimate_cost("openai/gpt-oss-20b", 1_000_000, 1_000_000) == 0.0


def test_estimate_cost_unknown_model() -> None:
    assert estimate_cost("some-unknown-model", 100, 100) is None


def test_format_usage_free() -> None:
    t = UsageTracker(calls=3, prompt_tokens=1000, completion_tokens=500)
    text = format_usage(t, "openai/gpt-oss-20b")
    assert "miễn phí" in text
    assert "1,500" in text  # total tokens


def test_format_usage_unknown_cost() -> None:
    t = UsageTracker(calls=1, prompt_tokens=10, completion_tokens=5)
    text = format_usage(t, "mystery-model")
    assert "không rõ" in text
