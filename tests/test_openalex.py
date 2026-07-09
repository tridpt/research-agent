"""Tests for the OpenAlex lookup tool: parsing, formatting, and wiring."""
from __future__ import annotations

import pytest

from research_agent.decision import parse_decision
from research_agent.models import ActionType, AgentDecision
from research_agent.openalex import (
    OpenAlexError,
    format_works,
    normalize_query,
    parse_works,
    works_params,
)
from research_agent.tools import TOOL_SCHEMAS

_WORKS_OK = {
    "results": [
        {
            "id": "https://openalex.org/W1",
            "doi": "https://doi.org/10.1234/abc",
            "title": "Attention Is All You Need",
            "publication_year": 2017,
            "authorships": [
                {"author": {"display_name": "Ashish Vaswani"}},
                {"author": {"display_name": "Noam Shazeer"}},
            ],
            "primary_location": {"source": {"display_name": "NeurIPS"}},
        },
        {
            "id": "https://openalex.org/W2",
            "doi": None,
            "title": "A Second Work",
            "publication_year": 2020,
            "authorships": [{"author": {"display_name": "Jane Roe"}}],
            "primary_location": {"landing_page_url": "https://example.org/paper2"},
        },
    ]
}


def test_normalize_query_collapses_and_rejects_empty() -> None:
    assert normalize_query("  deep   learning ") == "deep learning"
    with pytest.raises(OpenAlexError):
        normalize_query("   ")


def test_works_params_shape() -> None:
    params = works_params("transformers", per_page=5)
    assert params["search"] == "transformers"
    assert params["per_page"] == 5
    assert "authorships" in params["select"]


def test_works_params_floors_per_page_at_one() -> None:
    assert works_params("x", per_page=0)["per_page"] == 1


def test_parse_works_extracts_fields_and_prefers_doi() -> None:
    works = parse_works(_WORKS_OK)
    assert [w.title for w in works] == ["Attention Is All You Need", "A Second Work"]
    assert works[0].authors == ("Ashish Vaswani", "Noam Shazeer")
    assert works[0].venue == "NeurIPS"
    assert works[0].year == "2017"
    assert works[0].url == "https://doi.org/10.1234/abc"


def test_parse_works_falls_back_to_landing_page() -> None:
    works = parse_works(_WORKS_OK)
    assert works[1].url == "https://example.org/paper2"


def test_parse_works_bare_doi_gets_https_prefix() -> None:
    payload = {"results": [{"title": "T", "doi": "10.5/xyz"}]}
    assert parse_works(payload)[0].url == "https://doi.org/10.5/xyz"


def test_parse_works_empty_raises() -> None:
    with pytest.raises(OpenAlexError):
        parse_works({"results": []})


def test_parse_works_malformed_raises() -> None:
    with pytest.raises(OpenAlexError):
        parse_works("nope")


def test_parse_works_skips_untitled() -> None:
    with pytest.raises(OpenAlexError):
        parse_works({"results": [{"title": ""}]})


def test_format_works_includes_meta_and_url() -> None:
    out = format_works(parse_works(_WORKS_OK))
    assert out.startswith("OpenAlex results:")
    assert "Attention Is All You Need" in out
    assert "NeurIPS" in out
    assert "https://doi.org/10.1234/abc" in out


def test_format_works_truncates_author_list() -> None:
    payload = {
        "results": [
            {
                "title": "Many authors",
                "authorships": [{"author": {"display_name": f"A{i}"}} for i in range(6)],
                "publication_year": 2021,
            }
        ]
    }
    assert "et al." in format_works(parse_works(payload))


def test_parse_decision_accepts_openalex_search() -> None:
    decision = parse_decision({"action": "openalex_search", "query": "transformers"})
    assert isinstance(decision, AgentDecision)
    assert decision.action is ActionType.OPENALEX_SEARCH
    assert decision.openalex_query == "transformers"


def test_parse_decision_rejects_openalex_search_without_query() -> None:
    assert not isinstance(parse_decision({"action": "openalex_search"}), AgentDecision)


def test_openalex_tool_is_advertised() -> None:
    names = {t["function"]["name"] for t in TOOL_SCHEMAS}
    assert "openalex_search" in names
