"""Tests for the optional on-disk LLM response cache."""
from __future__ import annotations

from pathlib import Path

from research_agent.llm import Message
from research_agent.llm_cache import CachingLLMProvider, LLMResponseCache, llm_cache_key

from .fakes import ScriptedLLM


def _msgs(text: str) -> list[Message]:
    return [Message(role="user", content=text)]


def test_llm_cache_key_stable_and_distinct() -> None:
    a = llm_cache_key("m", _msgs("hello"), ())
    b = llm_cache_key("m", _msgs("hello"), ())
    c = llm_cache_key("m", _msgs("world"), ())
    assert a == b
    assert a != c


def test_cache_roundtrip(tmp_path: Path) -> None:
    cache = LLMResponseCache(tmp_path)
    assert cache.get("text", "k") is None
    cache.put("text", "k", "value")
    assert cache.get("text", "k") == "value"


def test_caching_provider_generate_serves_second_call_from_cache(tmp_path: Path) -> None:
    inner = ScriptedLLM(decisions=[], text="generated answer")
    provider = CachingLLMProvider(inner, LLMResponseCache(tmp_path), model="m")

    first = provider.generate(_msgs("q"))
    second = provider.generate(_msgs("q"))
    assert first == second == "generated answer"
    assert provider.hits == 1 and provider.misses == 1
    assert inner.generate_calls == 1  # inner called only once


def test_caching_provider_decide_action_is_cached(tmp_path: Path) -> None:
    inner = ScriptedLLM(decisions=[{"action": "search", "query": "x"}])
    provider = CachingLLMProvider(inner, LLMResponseCache(tmp_path), model="m")

    d1 = provider.decide_action(_msgs("q"), [])
    d2 = provider.decide_action(_msgs("q"), [])
    assert d1 == d2 == {"action": "search", "query": "x"}
    assert inner.decide_calls == 1
