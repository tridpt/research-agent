"""Tests for the CrossRef tool: parsing, formatting, and wiring."""
from __future__ import annotations

import pytest

from research_agent.crossref import (
    CrossRefError,
    format_works,
    normalize_query,
    parse_crossref,
)
from research_agent.decision import parse_decision
from research_agent.models import ActionType, AgentDecision
from research_agent.tools import TOOL_SCHEMAS

_PAYLOAD = {
    "message": {
        "items": [
            {
                "title": ["Attention Is All You Need"],
                "author": [{"given": "Ashish", "family": "Vaswani"}, {"given": "Noam", "family": "Shazeer"}],
                "issued": {"date-parts": [[2017, 6]]},
                "DOI": "10.5555/3295222.3295349",
                "container-title": ["NeurIPS"],
            }
        ]
    }
}


def test_normalize_query_rejects_empty() -> None:
    assert normalize_query("  transformer  models ") == "transformer models"
    with pytest.raises(CrossRefError):
        normalize_query("")


def test_parse_crossref_extracts_work() -> None:
    works = parse_crossref(_PAYLOAD)
    w = works[0]
    assert w.title == "Attention Is All You Need"
    assert w.authors == ("Ashish Vaswani", "Noam Shazeer")
    assert w.year == "2017"
    assert w.doi.startswith("10.5555")
    assert w.container == "NeurIPS"


def test_parse_crossref_no_items_raises() -> None:
    with pytest.raises(CrossRefError):
        parse_crossref({"message": {"items": []}})


def test_format_works_includes_doi_link() -> None:
    out = format_works(parse_crossref(_PAYLOAD))
    assert "CrossRef results:" in out
    assert "Attention Is All You Need" in out
    assert "https://doi.org/10.5555/3295222.3295349" in out


def test_parse_decision_accepts_crossref_search() -> None:
    d = parse_decision({"action": "crossref_search", "query": "transformers"})
    assert isinstance(d, AgentDecision)
    assert d.action is ActionType.CROSSREF_SEARCH
    assert d.doi_query == "transformers"


def test_crossref_tool_is_advertised() -> None:
    assert "crossref_search" in {t["function"]["name"] for t in TOOL_SCHEMAS}
