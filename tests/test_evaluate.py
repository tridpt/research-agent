"""Tests for the evaluation harness."""
from __future__ import annotations

from research_agent.evaluate import aggregate, evaluate_report
from research_agent.models import Citation, Report, Source


def _report(urls, citations, no_info=False, body="body text"):
    return Report(
        question="q",
        body_markdown=body,
        citations=tuple(Citation(claim_ref=f"c{i}", url=u) for i, u in enumerate(citations)),
        sources=tuple(Source(url=u, content="", fetched_at=0.0) for u in urls),
        no_information=no_info,
    )


def test_evaluate_counts_sources_domains_citations() -> None:
    m = evaluate_report(_report(
        ["https://a.com/1", "https://a.com/2", "https://b.com/x"],
        ["https://a.com/1", "https://b.com/x"],
    ))
    assert m.n_sources == 3
    assert m.n_domains == 2
    assert m.n_citations == 2
    assert m.grounded is True
    assert m.has_information is True


def test_evaluate_no_info_report() -> None:
    m = evaluate_report(_report([], [], no_info=True))
    assert m.n_sources == 0
    assert m.grounded is False
    assert m.has_information is False


def test_evaluate_sources_without_citations_not_grounded() -> None:
    m = evaluate_report(_report(["https://a.com"], []))
    assert m.n_sources == 1
    assert m.grounded is False


def test_aggregate_averages() -> None:
    metrics = [
        evaluate_report(_report(["https://a.com", "https://b.com"], ["https://a.com"])),
        evaluate_report(_report(["https://c.com"], [])),
    ]
    agg = aggregate(metrics)
    assert agg["avg_sources"] == 1.5
    assert agg["avg_domains"] == 1.5
    assert agg["grounded_rate"] == 0.5


def test_aggregate_empty() -> None:
    agg = aggregate([])
    assert agg["avg_sources"] == 0.0
    assert agg["grounded_rate"] == 0.0
