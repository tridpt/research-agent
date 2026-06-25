"""Tests for recency detection."""
from __future__ import annotations

from research_agent.recency import recency_directive, wants_recency


def test_wants_recency_detects_english_cues() -> None:
    assert wants_recency("What is the latest version of Python?")
    assert wants_recency("current state of solid-state batteries")
    assert wants_recency("recent advances in fusion")


def test_wants_recency_detects_vietnamese_cues() -> None:
    assert wants_recency("Tin tức mới nhất về AI")
    assert wants_recency("Tình hình hiện tại của kinh tế")


def test_wants_recency_detects_recent_year() -> None:
    assert wants_recency("State of LLM agents in 2026")
    assert not wants_recency("History of the Roman empire in 1850")


def test_wants_recency_false_for_timeless_question() -> None:
    assert not wants_recency("What is the CAP theorem?")
    assert not wants_recency("How does HTTPS work?")


def test_recency_directive_mentions_freshness() -> None:
    directive = recency_directive()
    assert "recent" in directive.lower()
    assert "NOW" in directive
