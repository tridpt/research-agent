"""Tests for deterministic, explainable source-quality signals."""
from __future__ import annotations

from research_agent.agent import build_messages
from research_agent.models import Report, SearchResult, Source
from research_agent.render import render_markdown
from research_agent.source_quality import assess_source, rank_search_results, source_quality_summary


def test_assess_source_prefers_official_evidence_rich_content() -> None:
    official = assess_source("https://www.nasa.gov/climate", "evidence " * 100)
    social = assess_source("https://www.reddit.com/r/weather", "short")

    assert official.label == "high"
    assert "official" in official.reason
    assert social.label == "low"
    assert "social" in social.reason


def test_weather_direct_reading_is_not_penalized_for_being_concise() -> None:
    quality = assess_source("https://wttr.in/Hanoi?format=3", "Hanoi: +33°C")

    assert quality.label == "medium"
    assert "direct data provider" in quality.reason


def test_rank_search_results_places_better_domain_first() -> None:
    social = SearchResult(title="Discussion", url="https://reddit.com/r/topic", snippet="opinions")
    official = SearchResult(title="Agency", url="https://agency.gov/report", snippet="data")

    assert rank_search_results([social, official]) == (official, social)


def test_agent_and_report_expose_source_quality() -> None:
    source = Source(url="https://example.gov/data", content="data " * 200, fetched_at=0.0)
    messages = build_messages("q", [], [SearchResult("Agency", source.url, "data")])
    report = Report(question="q", body_markdown="body", sources=(source,))

    assert "QUALITY: high" in messages[-2].content
    assert "Quality: high" in render_markdown(report)
    assert source_quality_summary(source).score >= 75
