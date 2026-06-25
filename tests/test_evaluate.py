"""Tests for the evaluation harness."""
from __future__ import annotations

from research_agent.evaluate import (
    aggregate,
    compare_modes,
    evaluate_modes,
    evaluate_report,
    format_comparison_markdown,
    llm_quality_score,
    parse_quality_judgement,
)
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
    assert agg["info_rate"] == 0.0


def test_evaluate_report_averages_source_quality() -> None:
    m = evaluate_report(_report(["https://example.gov/data", "https://reddit.com/r/x"], []))
    # One official (high) + one social (low) domain -> a mid-range average.
    assert 0.0 < m.avg_source_quality < 100.0


def test_evaluate_modes_runs_each_runner_over_questions() -> None:
    def normal(q: str) -> Report:
        return _report(["https://a.com"], ["https://a.com"], body=f"answer to {q}")

    def reflect(q: str) -> Report:
        return _report(["https://a.com", "https://b.com"], ["https://a.com", "https://b.com"])

    results = evaluate_modes(["q1", "q2"], {"normal": normal, "reflect": reflect})
    assert set(results) == {"normal", "reflect"}
    assert len(results["normal"]) == 2
    assert results["reflect"][0].n_domains == 2


def test_compare_and_format_comparison_markdown() -> None:
    results = evaluate_modes(
        ["q"],
        {
            "normal": lambda q: _report(["https://a.com"], ["https://a.com"]),
            "reflect": lambda q: _report(["https://a.com", "https://b.com"], ["https://a.com"]),
        },
    )
    summary = compare_modes(results)
    table = format_comparison_markdown(summary)
    assert "| Mode |" in table
    assert "normal" in table
    assert "reflect" in table


def test_format_comparison_markdown_handles_empty() -> None:
    assert "No evaluation results" in format_comparison_markdown({})


def test_parse_quality_judgement_valid_and_clamped() -> None:
    j = parse_quality_judgement('{"score": 8, "rationale": "well grounded"}')
    assert j.score == 8
    assert j.rationale == "well grounded"
    # Out-of-range scores clamp into [0, 10].
    assert parse_quality_judgement({"score": 99}).score == 10
    assert parse_quality_judgement({"score": -5}).score == 0


def test_parse_quality_judgement_malformed_is_conservative() -> None:
    assert parse_quality_judgement("not json").score == 0
    assert parse_quality_judgement({"nope": 1}).score == 0


class _JudgeLLM:
    def __init__(self, raw: str) -> None:
        self._raw = raw

    def generate(self, messages) -> str:
        return self._raw


def test_llm_quality_score_uses_provider() -> None:
    report = _report(["https://a.com"], ["https://a.com"], body="An answer [1].")
    judgement = llm_quality_score(report, _JudgeLLM('{"score": 7, "rationale": "ok"}'))
    assert judgement.score == 7
    assert judgement.rationale == "ok"
