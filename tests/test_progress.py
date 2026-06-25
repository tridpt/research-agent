"""Tests for the CLI budget-progress line and budget-aware emitter."""
from __future__ import annotations

import io

from research_agent.models import ResearchBudget, TraceEvent, TraceEventType
from research_agent.observability import TraceEmitter, format_budget_progress


def test_format_budget_progress() -> None:
    budget = ResearchBudget(max_rounds=8, max_sources=12)
    line = format_budget_progress(2, 5, budget)
    assert "round 2/8" in line
    assert "sources 5/12" in line


def test_emitter_appends_progress_on_round_completed() -> None:
    stream = io.StringIO()
    emit = TraceEmitter(verbose=True, stream=stream, budget=ResearchBudget(max_rounds=8, max_sources=12))
    emit(TraceEvent(type=TraceEventType.ROUND_COMPLETED, round_index=1, sources_count=2))
    out = stream.getvalue()
    assert "progress: round 1/8" in out


def test_emitter_without_budget_has_no_progress_line() -> None:
    stream = io.StringIO()
    emit = TraceEmitter(verbose=True, stream=stream)
    emit(TraceEvent(type=TraceEventType.ROUND_COMPLETED, round_index=1, sources_count=2))
    assert "progress:" not in stream.getvalue()
