"""Tests for the multi-agent (planner / researcher / writer) orchestration."""
from __future__ import annotations

from research_agent.config import ENV_API_KEY, resolve_settings
from research_agent.models import SearchResult, Settings, Source
from research_agent.multi_agent import (
    dedupe_sources,
    make_plan,
    parse_plan,
    run_multi_agent,
)
from research_agent.search_tool import SearchOutcome
from research_agent.synthesizer import synthesize

from .fakes import FakeFetch, FakeSearch


def _settings(**over) -> Settings:
    base = {"max_rounds": 6, "max_sources": 6, "min_domains": 1}
    base.update(over)
    return resolve_settings(env={ENV_API_KEY: "k"}, cli_overrides=base)


# ---- parse_plan ----
def test_parse_plan_valid() -> None:
    subs = parse_plan({"sub_questions": ["a", "b", "c"]}, "q")
    assert subs == ("a", "b", "c")


def test_parse_plan_from_json_string() -> None:
    assert parse_plan('{"sub_questions": ["x"]}', "q") == ("x",)


def test_parse_plan_caps_count() -> None:
    subs = parse_plan({"sub_questions": ["1", "2", "3", "4", "5", "6"]}, "q", max_sub_questions=3)
    assert len(subs) == 3


def test_parse_plan_falls_back_to_question() -> None:
    assert parse_plan("garbage", "the original q") == ("the original q",)
    assert parse_plan({"sub_questions": []}, "the original q") == ("the original q",)
    assert parse_plan(12345, "the original q") == ("the original q",)


# ---- dedupe_sources ----
def test_dedupe_sources_removes_duplicates_preserving_order() -> None:
    g1 = [Source(url="https://a.com", content="", fetched_at=0.0)]
    g2 = [
        Source(url="https://a.com", content="", fetched_at=0.0),  # dup
        Source(url="https://b.com", content="", fetched_at=0.0),
    ]
    merged = dedupe_sources([g1, g2])
    assert [s.url for s in merged] == ["https://a.com", "https://b.com"]


# ---- planner agent ----
def test_make_plan_uses_llm() -> None:
    class PlanLLM:
        def decide_action(self, m, t):
            return {"action": "finish"}

        def generate(self, m):
            return '{"sub_questions": ["sub one", "sub two"]}'

    assert make_plan("q", PlanLLM()) == ("sub one", "sub two")


# ---- end-to-end orchestration ----
class _MultiLLM:
    """Planner returns sub-questions; researchers read one source each."""

    def __init__(self):
        self._reads = {
            "sub one": "https://a.com/x",
            "sub two": "https://b.com/y",
        }

    def decide_action(self, messages, tools):
        # Find the current sub-question from the research-question message.
        q = ""
        for m in messages:
            if m.content.startswith("Research question: "):
                q = m.content.split("Research question: ", 1)[1]
        url = self._reads.get(q)
        # Search first, then read one approved result for each sub-question.
        joined = " ".join(m.content for m in messages)
        if "Search results found so far" not in joined:
            return {"action": "search", "query": q}
        if url and url not in joined.split("Source URL: ")[-1][:80]:
            # crude: if we haven't shown the source yet, read it
            if "Source URL:" not in joined:
                return {"action": "read", "url": url}
        return {"action": "finish"}

    def generate(self, messages):
        sys = messages[0].content if messages else ""
        if "research planner" in sys:
            return '{"sub_questions": ["sub one", "sub two"]}'
        return "Final report [1] [2]"


def test_run_multi_agent_collects_across_subquestions() -> None:
    report = run_multi_agent(
        question="big question",
        settings=_settings(),
        llm=_MultiLLM(),
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
        max_sub_questions=4,
    )
    urls = {s.url for s in report.sources}
    assert "https://a.com/x" in urls and "https://b.com/y" in urls
