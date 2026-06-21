"""Tests for the reflection (self-critique) loop."""
from __future__ import annotations

from research_agent.config import ENV_API_KEY, resolve_settings
from research_agent.models import SearchResult, Settings
from research_agent.reflection import (
    Critique,
    ReflectionVerdict,
    decide_reflection,
    format_directive,
    parse_critique,
    run_with_reflection,
)
from research_agent.search_tool import SearchOutcome
from research_agent.synthesizer import synthesize

from .fakes import FakeFetch, FakeSearch


def _settings(**over) -> Settings:
    base = {"max_rounds": 8, "max_sources": 8, "min_domains": 1}
    base.update(over)
    return resolve_settings(env={ENV_API_KEY: "k"}, cli_overrides=base)


# ---- parse_critique ----
def test_parse_critique_valid() -> None:
    c = parse_critique({"score": 7, "gaps": ["x"], "follow_up_queries": ["q1", "q2"]})
    assert c.score == 7 and c.gaps == ("x",) and c.follow_up_queries == ("q1", "q2")


def test_parse_critique_from_json_string() -> None:
    c = parse_critique('{"score": 9, "gaps": [], "follow_up_queries": []}')
    assert c.score == 9


def test_parse_critique_clamps_and_defaults() -> None:
    assert parse_critique({"score": 99}).score == 10
    assert parse_critique({"score": -5}).score == 0
    assert parse_critique("not json").score == 0
    assert parse_critique(12345).score == 0


# ---- decide_reflection ----
def test_decide_reflection_accepts_high_score() -> None:
    d = decide_reflection(Critique(score=9, follow_up_queries=("q",)), iteration=0, max_iterations=2, accept_score=8)
    assert d.verdict is ReflectionVerdict.ACCEPT


def test_decide_reflection_revises_low_score() -> None:
    d = decide_reflection(Critique(score=4, follow_up_queries=("q",)), iteration=0, max_iterations=2, accept_score=8)
    assert d.verdict is ReflectionVerdict.REVISE
    assert d.follow_up_queries == ("q",)


def test_decide_reflection_accepts_at_iteration_cap() -> None:
    d = decide_reflection(Critique(score=2, follow_up_queries=("q",)), iteration=2, max_iterations=2, accept_score=8)
    assert d.verdict is ReflectionVerdict.ACCEPT


def test_decide_reflection_accepts_without_followups() -> None:
    d = decide_reflection(Critique(score=2, follow_up_queries=()), iteration=0, max_iterations=2, accept_score=8)
    assert d.verdict is ReflectionVerdict.ACCEPT


def test_format_directive_includes_gaps_and_queries() -> None:
    text = format_directive(Critique(score=3, gaps=("missing X",), follow_up_queries=("find X",)))
    assert "missing X" in text and "find X" in text


# ---- end-to-end reflection loop with fakes ----
class _CritiqueLLM:
    """LLM that drives the base loop and returns scripted critique JSON."""

    def __init__(self, decisions, critiques):
        self._decisions = list(decisions)
        self._critiques = list(critiques)
        self.generate_calls = 0

    def decide_action(self, messages, tools):
        if self._decisions:
            return self._decisions.pop(0)
        return {"action": "finish"}

    def generate(self, messages):
        self.generate_calls += 1
        # Distinguish synthesis vs critique by the system prompt content.
        sys_msg = messages[0].content if messages else ""
        if "critical reviewer" in sys_msg:
            if self._critiques:
                return self._critiques.pop(0)
            return '{"score": 10, "gaps": [], "follow_up_queries": []}'
        return "Synthesized answer [https://a.com/x]"


def test_run_with_reflection_accepts_when_satisfied() -> None:
    llm = _CritiqueLLM(
        decisions=[
            {"action": "search", "query": "topic"},
            {"action": "read", "url": "https://a.com/x"},
            {"action": "finish"},
        ],
        critiques=['{"score": 9, "gaps": [], "follow_up_queries": []}'],
    )
    report = run_with_reflection(
        question="q",
        settings=_settings(),
        llm=llm,
        search=FakeSearch(
            SearchOutcome(results=(SearchResult(title="A", url="https://a.com/x", snippet=""),))
        ),
        fetch=FakeFetch(),
        synthesize_fn=synthesize,
        clock=lambda: 0.0,
        emit=lambda e: None,
        max_iterations=2,
    )
    assert report.sources  # collected at least one source


def test_run_with_reflection_revises_then_accepts() -> None:
    # First critique is low (forces a revise), second is high (accept).
    llm = _CritiqueLLM(
        decisions=[
            {"action": "search", "query": "topic"},
            {"action": "read", "url": "https://a.com/x"},
            {"action": "finish"},
            {"action": "read", "url": "https://b.com/y"},
            {"action": "finish"},
        ],
        critiques=[
            '{"score": 3, "gaps": ["needs more"], "follow_up_queries": ["more"]}',
            '{"score": 9, "gaps": [], "follow_up_queries": []}',
        ],
    )
    report = run_with_reflection(
        question="q",
        settings=_settings(),
        llm=llm,
        search=FakeSearch(
            SearchOutcome(
                results=(
                    SearchResult(title="A", url="https://a.com/x", snippet=""),
                    SearchResult(title="B", url="https://b.com/y", snippet=""),
                )
            )
        ),
        fetch=FakeFetch(),
        synthesize_fn=synthesize,
        clock=lambda: 0.0,
        emit=lambda e: None,
        max_iterations=2,
    )
    # Both sources collected across the two research passes.
    urls = {s.url for s in report.sources}
    assert "https://a.com/x" in urls and "https://b.com/y" in urls
