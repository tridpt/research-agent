"""Tests for the arXiv tool: Atom parsing, formatting, and wiring."""
from __future__ import annotations

import pytest

from research_agent.arxiv import (
    ArxivError,
    format_papers,
    normalize_query,
    parse_arxiv_atom,
)
from research_agent.decision import parse_decision
from research_agent.models import ActionType, AgentDecision
from research_agent.tools import TOOL_SCHEMAS

_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2005.11401v4</id>
    <published>2020-05-22T20:23:18Z</published>
    <title>Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks</title>
    <summary>We explore a general-purpose fine-tuning recipe for retrieval.</summary>
    <author><name>Patrick Lewis</name></author>
    <author><name>Ethan Perez</name></author>
  </entry>
</feed>
"""


def test_normalize_query_collapses_whitespace_and_rejects_empty() -> None:
    assert normalize_query("  retrieval   augmented  ") == "retrieval augmented"
    with pytest.raises(ArxivError):
        normalize_query("   ")


def test_parse_arxiv_atom_extracts_paper() -> None:
    papers = parse_arxiv_atom(_FEED)
    assert len(papers) == 1
    p = papers[0]
    assert p.title.startswith("Retrieval-Augmented Generation")
    assert p.authors == ("Patrick Lewis", "Ethan Perez")
    assert p.url.endswith("2005.11401v4")
    assert p.published == "2020-05-22"


def test_parse_arxiv_atom_empty_feed_raises() -> None:
    with pytest.raises(ArxivError):
        parse_arxiv_atom('<feed xmlns="http://www.w3.org/2005/Atom"></feed>')


def test_parse_arxiv_atom_invalid_xml_raises() -> None:
    with pytest.raises(ArxivError):
        parse_arxiv_atom("not xml <<<")


def test_format_papers_lists_title_and_authors() -> None:
    out = format_papers(parse_arxiv_atom(_FEED))
    assert "arXiv results:" in out
    assert "Retrieval-Augmented Generation" in out
    assert "Patrick Lewis" in out


def test_parse_decision_accepts_arxiv_search() -> None:
    decision = parse_decision({"action": "arxiv_search", "query": "RAG"})
    assert isinstance(decision, AgentDecision)
    assert decision.action is ActionType.ARXIV_SEARCH
    assert decision.paper_query == "RAG"


def test_parse_decision_rejects_arxiv_without_query() -> None:
    assert not isinstance(parse_decision({"action": "arxiv_search"}), AgentDecision)


def test_arxiv_tool_is_advertised() -> None:
    assert "arxiv_search" in {t["function"]["name"] for t in TOOL_SCHEMAS}
