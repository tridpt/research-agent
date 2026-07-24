"""Unit tests for the pure agent-step renderer extracted from app.py."""
from __future__ import annotations

from ui.steps import render_step

from research_agent.models import TraceEvent, TraceEventType


def _action(action: str, **detail) -> TraceEvent:
    return TraceEvent(
        type=TraceEventType.ACTION_SELECTED,
        round_index=1,
        sources_count=0,
        detail={"action": action, **detail},
    )


def test_render_step_search_bilingual() -> None:
    ev = _action("search", query="cats")
    assert "cats" in render_step(ev, "vi")
    assert "Searching the web" in render_step(ev, "en")


def test_render_step_read_shows_url() -> None:
    ev = _action("read", url="https://a.com/x")
    assert "https://a.com/x" in render_step(ev, "en")


def test_render_step_unknown_action_falls_back() -> None:
    assert "custom_tool" in render_step(_action("custom_tool"), "en")


def test_render_step_round_completed() -> None:
    ev = TraceEvent(type=TraceEventType.ROUND_COMPLETED, round_index=2, sources_count=3)
    assert "Round 2 done" in render_step(ev, "en")
    assert "vòng 2" in render_step(ev, "vi")


def test_render_step_error_classification() -> None:
    ev = TraceEvent(
        type=TraceEventType.TOOL_ERROR,
        round_index=1,
        sources_count=0,
        detail={"error": "fetch failed for https://x"},
    )
    assert "load" in render_step(ev, "en").lower()
