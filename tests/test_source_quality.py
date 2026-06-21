"""Tests for deterministic, explainable source-quality signals."""
from __future__ import annotations

from research_agent.agent import build_messages
from research_agent.models import Report, SearchResult, Source
from research_agent.render import render_markdown
from research_agent.source_quality import (
    assess_source,
    rank_search_results,
    source_display_name,
    source_quality_summary,
)


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


def test_local_pdf_has_safe_label_and_high_quality() -> None:
    url = "local-pdf://project%20brief.pdf"
    quality = assess_source(url, "PDF evidence " * 100)

    assert quality.label == "high"
    assert quality.score == 100
    assert source_display_name(url) == "User-provided PDF: project brief.pdf"


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


def test_report_renders_pdf_name_without_local_path() -> None:
    source = Source(
        url="local-pdf://project%20brief.pdf",
        content="User-provided PDF: project brief.pdf\nPages: 2\n\nEvidence",
        fetched_at=0.0,
    )
    report = Report(question="q", body_markdown="Answer [1]", sources=(source,))
    markdown = render_markdown(report)

    assert "User-provided PDF: project brief.pdf" in markdown
    assert "local-pdf://project%20brief.pdf" in markdown
    assert "C:\\Users" not in markdown
