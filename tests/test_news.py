"""Tests for the news tool: Hacker News parsing, formatting, and wiring."""
from __future__ import annotations

import pytest

from research_agent.decision import parse_decision
from research_agent.models import ActionType, AgentDecision
from research_agent.news import (
    NewsError,
    format_news,
    normalize_query,
    parse_hn_results,
)
from research_agent.tools import TOOL_SCHEMAS

_PAYLOAD = {
    "nbHits": 2,
    "hits": [
        {
            "title": "OpenAI ships a new model",
            "url": "https://example.com/openai",
            "points": 512,
            "num_comments": 130,
            "created_at": "2026-06-20T10:00:00Z",
            "objectID": "111",
        },
        {
            "title": "Story without url",
            "points": 10,
            "num_comments": 2,
            "created_at": "2026-06-19T08:00:00Z",
            "objectID": "222",
        },
    ],
}


def test_normalize_query_rejects_empty() -> None:
    with pytest.raises(NewsError):
        normalize_query("  ")


def test_parse_hn_results_extracts_items() -> None:
    items = parse_hn_results(_PAYLOAD)
    assert len(items) == 2
    assert items[0].title == "OpenAI ships a new model"
    assert items[0].points == 512
    assert items[0].created_at == "2026-06-20"
    # An item without a url falls back to its HN discussion link.
    assert items[1].discussion_url.endswith("id=222")


def test_parse_hn_results_respects_limit() -> None:
    assert len(parse_hn_results(_PAYLOAD, limit=1)) == 1


def test_parse_hn_results_no_hits_raises() -> None:
    with pytest.raises(NewsError):
        parse_hn_results({"hits": []})


def test_format_news_includes_metadata() -> None:
    out = format_news(parse_hn_results(_PAYLOAD))
    assert "Recent stories (Hacker News):" in out
    assert "512 points" in out
    assert "OpenAI ships a new model" in out


def test_parse_decision_accepts_get_news() -> None:
    decision = parse_decision({"action": "get_news", "query": "AI safety"})
    assert isinstance(decision, AgentDecision)
    assert decision.action is ActionType.GET_NEWS
    assert decision.news_query == "AI safety"


def test_get_news_tool_is_advertised() -> None:
    assert "get_news" in {t["function"]["name"] for t in TOOL_SCHEMAS}
