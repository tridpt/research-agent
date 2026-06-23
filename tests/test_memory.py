"""Tests for long-term memory across sessions."""
from __future__ import annotations

from pathlib import Path

from research_agent.memory import (
    MemoryRecord,
    MemoryStore,
    format_memory_directive,
    relevance_score,
    select_relevant,
    summarize_for_memory,
    tokenize,
)
from research_agent.models import Citation, Report, Source


def _report(question: str, body: str = "Some finding [1].", urls=("https://a.com",)) -> Report:
    return Report(
        question=question,
        body_markdown=body,
        citations=tuple(Citation(claim_ref=f"c{i}", url=u) for i, u in enumerate(urls)),
        sources=tuple(Source(url=u, content="", fetched_at=0.0) for u in urls),
    )


def test_tokenize_drops_stopwords_and_short_words() -> None:
    tokens = tokenize("What is the CAP theorem in distributed systems?")
    assert "cap" in tokens
    assert "theorem" in tokens
    assert "the" not in tokens
    assert "is" not in tokens


def test_relevance_score_higher_for_overlapping_questions() -> None:
    record = MemoryRecord(question="What is the CAP theorem in distributed systems?", summary="")
    related = relevance_score("Explain the CAP theorem for distributed databases", record)
    unrelated = relevance_score("How do I bake sourdough bread?", record)
    assert related > unrelated
    assert 0.0 <= related <= 1.0


def test_select_relevant_filters_and_ranks() -> None:
    records = [
        MemoryRecord(question="CAP theorem in distributed systems", summary="a"),
        MemoryRecord(question="SQL vs NoSQL databases", summary="b"),
        MemoryRecord(question="How to bake bread", summary="c"),
    ]
    chosen = select_relevant(records, "Explain the CAP theorem", k=2, min_score=0.1)
    assert chosen
    assert chosen[0].question == "CAP theorem in distributed systems"
    assert all("bread" not in r.question.lower() for r in chosen)


def test_select_relevant_excludes_exact_duplicate_question() -> None:
    records = [MemoryRecord(question="Same question", summary="x")]
    assert select_relevant(records, "Same question", k=3, min_score=0.0) == ()


def test_summarize_for_memory_flattens_and_caps() -> None:
    report = _report("q", body="# Title\n\n**Bold** text with `code` and lots of words. " * 50)
    summary = summarize_for_memory(report, max_chars=100)
    assert "#" not in summary
    assert len(summary) <= 101  # 100 + ellipsis


def test_format_memory_directive_empty_when_no_records() -> None:
    assert format_memory_directive(()) == ""


def test_format_memory_directive_lists_prior_questions() -> None:
    records = (MemoryRecord(question="Prior topic", summary="A short summary"),)
    directive = format_memory_directive(records)
    assert "Prior topic" in directive
    assert "A short summary" in directive


def test_memory_store_roundtrip_recall(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "mem.json")
    store.add(_report("CAP theorem in distributed systems"), now=1.0)
    store.add(_report("SQL vs NoSQL databases"), now=2.0)
    recalled = store.recall("Tell me about the CAP theorem", k=1, min_score=0.1)
    assert len(recalled) == 1
    assert "CAP" in recalled[0].question


def test_memory_store_skips_no_information_reports(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "mem.json")
    empty = Report(question="q", body_markdown="none", no_information=True)
    store.add(empty, now=1.0)
    assert store.load() == []
