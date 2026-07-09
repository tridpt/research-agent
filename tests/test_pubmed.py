"""Tests for the PubMed lookup tool: parsing, formatting, and wiring."""
from __future__ import annotations

import pytest

from research_agent.decision import parse_decision
from research_agent.models import ActionType, AgentDecision
from research_agent.pubmed import (
    PubMedError,
    esearch_params,
    esummary_params,
    format_articles,
    normalize_query,
    parse_esearch,
    parse_esummary,
)
from research_agent.tools import TOOL_SCHEMAS

_ESEARCH_OK = {"esearchresult": {"count": "2", "idlist": ["111", "222"]}}

_ESUMMARY_OK = {
    "result": {
        "uids": ["111", "222"],
        "111": {
            "uid": "111",
            "title": "Effects of aspirin on cardiovascular disease.",
            "authors": [{"name": "Smith J"}, {"name": "Doe A"}],
            "fulljournalname": "New England Journal of Medicine",
            "pubdate": "2023 Jan",
        },
        "222": {
            "uid": "222",
            "title": "A review of statins",
            "authors": [{"name": "Lee K"}],
            "source": "Lancet",
            "pubdate": "2022",
        },
    }
}


def test_normalize_query_collapses_and_rejects_empty() -> None:
    assert normalize_query("  aspirin   heart ") == "aspirin heart"
    with pytest.raises(PubMedError):
        normalize_query("   ")


def test_esearch_params_shape() -> None:
    params = esearch_params("aspirin", max_results=5)
    assert params["db"] == "pubmed"
    assert params["term"] == "aspirin"
    assert params["retmax"] == 5
    assert params["retmode"] == "json"


def test_esearch_params_floors_max_results_at_one() -> None:
    assert esearch_params("x", max_results=0)["retmax"] == 1


def test_esummary_params_joins_ids() -> None:
    assert esummary_params(("111", "222"))["id"] == "111,222"


def test_parse_esearch_returns_pmids() -> None:
    assert parse_esearch(_ESEARCH_OK) == ("111", "222")


def test_parse_esearch_empty_raises() -> None:
    with pytest.raises(PubMedError):
        parse_esearch({"esearchresult": {"idlist": []}})


def test_parse_esearch_malformed_raises() -> None:
    with pytest.raises(PubMedError):
        parse_esearch("not a dict")


def test_parse_esummary_orders_by_uids() -> None:
    articles = parse_esummary(_ESUMMARY_OK)
    assert [a.pmid for a in articles] == ["111", "222"]
    assert articles[0].title == "Effects of aspirin on cardiovascular disease"  # trailing dot stripped
    assert articles[0].authors == ("Smith J", "Doe A")
    assert articles[0].journal == "New England Journal of Medicine"
    assert articles[0].url == "https://pubmed.ncbi.nlm.nih.gov/111/"


def test_parse_esummary_falls_back_to_source_field() -> None:
    articles = parse_esummary(_ESUMMARY_OK)
    assert articles[1].journal == "Lancet"


def test_parse_esummary_skips_entries_without_title() -> None:
    payload = {"result": {"uids": ["1"], "1": {"uid": "1", "title": ""}}}
    with pytest.raises(PubMedError):
        parse_esummary(payload)


def test_parse_esummary_malformed_raises() -> None:
    with pytest.raises(PubMedError):
        parse_esummary({"nope": {}})


def test_format_articles_includes_meta_and_pmid() -> None:
    out = format_articles(parse_esummary(_ESUMMARY_OK))
    assert out.startswith("PubMed results:")
    assert "PMID 111" in out
    assert "New England Journal of Medicine" in out
    assert "Smith J" in out


def test_format_articles_truncates_author_list() -> None:
    payload = {
        "result": {
            "uids": ["1"],
            "1": {
                "uid": "1",
                "title": "Many authors",
                "authors": [{"name": f"A{i}"} for i in range(6)],
                "source": "J",
                "pubdate": "2020",
            },
        }
    }
    out = format_articles(parse_esummary(payload))
    assert "et al." in out


def test_parse_decision_accepts_pubmed_search() -> None:
    decision = parse_decision({"action": "pubmed_search", "query": "aspirin heart"})
    assert isinstance(decision, AgentDecision)
    assert decision.action is ActionType.PUBMED_SEARCH
    assert decision.pubmed_query == "aspirin heart"


def test_parse_decision_rejects_pubmed_search_without_query() -> None:
    assert not isinstance(parse_decision({"action": "pubmed_search"}), AgentDecision)


def test_pubmed_tool_is_advertised() -> None:
    names = {t["function"]["name"] for t in TOOL_SCHEMAS}
    assert "pubmed_search" in names
