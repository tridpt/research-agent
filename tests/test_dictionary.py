"""Tests for the dictionary tool: parsing, formatting, and wiring."""
from __future__ import annotations

import pytest

from research_agent.decision import parse_decision
from research_agent.dictionary import (
    DictionaryError,
    format_entry,
    normalize_word,
    parse_dictionary,
)
from research_agent.models import ActionType, AgentDecision
from research_agent.tools import TOOL_SCHEMAS

_PAYLOAD = [
    {
        "word": "hello",
        "phonetic": "/həˈloʊ/",
        "meanings": [
            {"partOfSpeech": "noun", "definitions": [{"definition": "A greeting."}]},
            {"partOfSpeech": "verb", "definitions": [{"definition": "To greet."}]},
        ],
    }
]


def test_normalize_word_keeps_letters_and_rejects_empty() -> None:
    assert normalize_word("  Hello! ") == "hello"
    with pytest.raises(DictionaryError):
        normalize_word("123 !!")


def test_parse_dictionary_extracts_definitions() -> None:
    entry = parse_dictionary(_PAYLOAD)
    assert entry.word == "hello"
    assert entry.phonetic == "/həˈloʊ/"
    assert len(entry.definitions) == 2
    assert entry.definitions[0].part_of_speech == "noun"


def test_parse_dictionary_not_found_raises() -> None:
    with pytest.raises(DictionaryError):
        parse_dictionary([])
    with pytest.raises(DictionaryError):
        parse_dictionary({"title": "No Definitions Found"})


def test_format_entry_lists_definitions() -> None:
    out = format_entry(parse_dictionary(_PAYLOAD))
    assert "Dictionary — hello" in out
    assert "(noun) A greeting." in out


def test_parse_decision_accepts_get_dictionary() -> None:
    d = parse_decision({"action": "get_dictionary", "word": "hello"})
    assert isinstance(d, AgentDecision)
    assert d.action is ActionType.GET_DICTIONARY
    assert d.word == "hello"


def test_dictionary_tool_is_advertised() -> None:
    assert "get_dictionary" in {t["function"]["name"] for t in TOOL_SCHEMAS}
