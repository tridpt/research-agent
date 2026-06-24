"""Tests for the Wikipedia lookup tool: parsing, formatting, and wiring."""
from __future__ import annotations

import pytest

from research_agent.decision import parse_decision
from research_agent.models import ActionType, AgentDecision
from research_agent.tools import TOOL_SCHEMAS
from research_agent.wikipedia import (
    WikipediaError,
    format_article,
    normalize_lang,
    normalize_topic,
    parse_wikipedia_response,
    wikipedia_query_params,
)


def _payload(pages: dict) -> dict:
    return {"batchcomplete": "", "query": {"pages": pages}}


_GOOD = _payload(
    {
        "1234": {
            "index": 1,
            "title": "CAP theorem",
            "fullurl": "https://en.wikipedia.org/wiki/CAP_theorem",
            "extract": "In database theory, the CAP theorem states that ...",
        }
    }
)


def test_normalize_topic_trims_and_rejects_empty() -> None:
    assert normalize_topic("  CAP theorem ") == "CAP theorem"
    with pytest.raises(WikipediaError):
        normalize_topic("   ")


def test_normalize_lang_defaults_and_sanitizes() -> None:
    assert normalize_lang(None) == "en"
    assert normalize_lang("") == "en"
    assert normalize_lang("VI") == "vi"
    assert normalize_lang("simple") == "simple"
    assert normalize_lang("zh-yue") == "zh-yue"  # keeps hyphen
    assert normalize_lang("en123/?") == "en"  # strips digits and punctuation


def test_wikipedia_query_params_uses_search_generator() -> None:
    params = wikipedia_query_params("CAP theorem")
    assert params["generator"] == "search"
    assert params["gsrsearch"] == "CAP theorem"
    assert params["explaintext"] == 1


def test_parse_wikipedia_response_picks_top_hit() -> None:
    article = parse_wikipedia_response(_GOOD)
    assert article.title == "CAP theorem"
    assert article.url.endswith("/CAP_theorem")
    assert "database theory" in article.extract


def test_parse_wikipedia_response_orders_by_index() -> None:
    payload = _payload(
        {
            "2": {"index": 2, "title": "Second", "extract": "second", "fullurl": "u2"},
            "1": {"index": 1, "title": "First", "extract": "first", "fullurl": "u1"},
        }
    )
    assert parse_wikipedia_response(payload).title == "First"


def test_parse_wikipedia_response_no_pages_raises() -> None:
    with pytest.raises(WikipediaError):
        parse_wikipedia_response({"query": {"pages": {}}})


def test_parse_wikipedia_response_empty_extract_raises() -> None:
    payload = _payload({"1": {"index": 1, "title": "T", "extract": "", "fullurl": "u"}})
    with pytest.raises(WikipediaError):
        parse_wikipedia_response(payload)


def test_format_article_titles_and_caps_length() -> None:
    article = parse_wikipedia_response(
        _payload({"1": {"index": 1, "title": "T", "extract": "x" * 100, "fullurl": "u"}})
    )
    out = format_article(article, max_chars=20)
    assert out.startswith("Wikipedia — T")
    assert out.endswith("…")


def test_parse_decision_accepts_get_wikipedia() -> None:
    decision = parse_decision({"action": "get_wikipedia", "topic": "CAP theorem"})
    assert isinstance(decision, AgentDecision)
    assert decision.action is ActionType.GET_WIKIPEDIA
    assert decision.topic == "CAP theorem"


def test_parse_decision_rejects_get_wikipedia_without_topic() -> None:
    assert not isinstance(parse_decision({"action": "get_wikipedia"}), AgentDecision)


def test_get_wikipedia_tool_is_advertised() -> None:
    names = {t["function"]["name"] for t in TOOL_SCHEMAS}
    assert "get_wikipedia" in names
