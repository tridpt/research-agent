"""Tests for the post-spec enhancements: cache, smart backoff, source diversity."""
from __future__ import annotations

from pathlib import Path

import pytest

from research_agent.agent import (
    count_distinct_domains,
    run_session,
    should_allow_finish,
)
from research_agent.cache import CachingFetchTool, FetchCache, cache_key, is_fresh
from research_agent.config import ENV_API_KEY, resolve_settings
from research_agent.errors import LLMError
from research_agent.fetch_tool import FetchOutcome
from research_agent.llm import TransientLLMError, parse_retry_after
from research_agent.models import SearchResult, Settings, Source
from research_agent.retry import call_with_retry, next_delay
from research_agent.search_tool import SearchOutcome
from research_agent.synthesizer import synthesize

from .fakes import FakeFetch, FakeSearch, ScriptedLLM


def _settings(**over) -> Settings:
    base = {"max_rounds": 12, "max_sources": 8}
    base.update(over)
    return resolve_settings(env={ENV_API_KEY: "k"}, cli_overrides=base)


# ---------------------------------------------------------------------------
# Fetch cache
# ---------------------------------------------------------------------------
def test_cache_key_is_stable_and_distinct() -> None:
    assert cache_key("https://a.com") == cache_key("https://a.com")
    assert cache_key("https://a.com") != cache_key("https://b.com")


def test_is_fresh() -> None:
    assert is_fresh(fetched_at=100.0, ttl_seconds=0, now=10_000) is True  # no expiry
    assert is_fresh(fetched_at=100.0, ttl_seconds=50, now=120) is True
    assert is_fresh(fetched_at=100.0, ttl_seconds=50, now=200) is False


def test_cache_roundtrip(tmp_path: Path) -> None:
    cache = FetchCache(tmp_path, ttl_seconds=0)
    assert cache.get("https://a.com") is None
    cache.put(Source(url="https://a.com", content="hello", fetched_at=1.0))
    got = cache.get("https://a.com")
    assert got is not None and got.content == "hello"


class _ExplodingFetch:
    def fetch(self, url: str) -> FetchOutcome:  # pragma: no cover
        raise AssertionError("inner fetch should not be called on a cache hit")


def test_caching_fetch_tool_serves_hit(tmp_path: Path) -> None:
    cache = FetchCache(tmp_path)
    cache.put(Source(url="https://a.com", content="cached", fetched_at=1.0))
    tool = CachingFetchTool(_ExplodingFetch(), cache)
    outcome = tool.fetch("https://a.com")
    assert outcome.ok and outcome.source.content == "cached"
    assert tool.hits == 1


def test_caching_fetch_tool_stores_miss(tmp_path: Path) -> None:
    cache = FetchCache(tmp_path)
    tool = CachingFetchTool(FakeFetch(), cache)
    first = tool.fetch("https://new.com/x")
    assert first.ok and tool.misses == 1
    # Now cached:
    assert cache.get("https://new.com/x") is not None


# ---------------------------------------------------------------------------
# Smart backoff
# ---------------------------------------------------------------------------
def test_parse_retry_after_seconds() -> None:
    assert parse_retry_after("5") == 5.0
    assert parse_retry_after("0") == 0.0
    assert parse_retry_after(None) is None
    assert parse_retry_after("garbage") is None


def test_parse_retry_after_http_date() -> None:
    # 60 seconds in the future relative to a fixed 'now'.
    from email.utils import formatdate

    now = 1_000_000.0
    header = formatdate(now + 60, usegmt=True)
    delay = parse_retry_after(header, now=now)
    assert delay is not None and 55 <= delay <= 65


def test_next_delay_prefers_retry_after() -> None:
    assert next_delay(attempt=1, base_delay=0.5, retry_after=7.0) == 7.0
    assert next_delay(attempt=3, base_delay=0.5, retry_after=None) == 2.0  # 0.5*2^2
    assert next_delay(attempt=10, base_delay=0.5, retry_after=None, max_delay=5.0) == 5.0
    assert next_delay(attempt=1, base_delay=0.5, retry_after=999, max_delay=30.0) == 30.0


def test_call_with_retry_honors_retry_after() -> None:
    delays: list[float] = []
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientLLMError("rate limited", retry_after=4.0)
        return "ok"

    result = call_with_retry(fn, max_attempts=5, sleep=delays.append, base_delay=0.5)
    assert result == "ok"
    assert delays == [4.0, 4.0]  # both retries waited the server-provided hint


def test_call_with_retry_clamps_sleep_to_remaining_deadline() -> None:
    delays: list[float] = []

    def fn():
        raise TransientLLMError("rate limited", retry_after=30.0)

    with pytest.raises(LLMError):
        call_with_retry(
            fn,
            max_attempts=3,
            sleep=delays.append,
            base_delay=0.5,
            time_left=lambda: 2.0,  # only 2s left; a 30s hint must be clamped
        )
    assert delays == [2.0, 2.0]


def test_call_with_retry_stops_when_deadline_passed() -> None:
    delays: list[float] = []
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise TransientLLMError("rate limited", retry_after=1.0)

    with pytest.raises(LLMError):
        call_with_retry(
            fn,
            max_attempts=5,
            sleep=delays.append,
            base_delay=0.5,
            time_left=lambda: 0.0,  # no time left: do not retry, do not sleep
        )
    assert calls["n"] == 1
    assert delays == []


# ---------------------------------------------------------------------------
# Source diversity: distinct domains + per-domain cap
# ---------------------------------------------------------------------------
def test_count_distinct_domains() -> None:
    sources = [
        Source(url="https://a.com/1", content="", fetched_at=0.0),
        Source(url="https://a.com/2", content="", fetched_at=0.0),
        Source(url="https://b.com/1", content="", fetched_at=0.0),
    ]
    assert count_distinct_domains(sources) == 2


def test_next_diversity_url() -> None:
    from research_agent.agent import next_diversity_url

    a = Source(url="https://a.com/1", content="", fetched_at=0.0)
    results = [
        SearchResult(title="a2", url="https://a.com/2", snippet=""),  # same domain
        SearchResult(title="b", url="https://b.com/1", snippet=""),   # new domain
    ]
    assert next_diversity_url([a], results, max_per_domain=2) == "https://b.com/1"
    # No new-domain results available -> None.
    assert next_diversity_url([a], [SearchResult("a", "https://a.com/9", "")], 2) is None
    # A new-domain URL that previously failed is excluded.
    assert next_diversity_url([a], results, 2, exclude_urls={"https://b.com/1"}) is None


def test_run_session_substitutes_unusable_read() -> None:
    # The LLM keeps choosing an already-read URL; the agent should auto-substitute
    # a fresh new-domain result instead of wasting every round.
    from research_agent.agent import count_distinct_domains, run_session

    llm = ScriptedLLM(
        decisions=[
            {"action": "search", "query": "topic"},
            {"action": "read", "url": "https://a.com/x"},
            {"action": "read", "url": "https://a.com/x"},  # duplicate -> substitute b
            {"action": "finish"},
        ]
    )
    search = FakeSearch(
        SearchOutcome(
            results=(
                SearchResult(title="A", url="https://a.com/x", snippet="s"),
                SearchResult(title="B", url="https://b.com/y", snippet="s"),
            )
        )
    )
    report = run_session(
        question="q",
        settings=_settings(min_domains=2, max_per_domain=1),
        llm=llm,
        search=search,
        fetch=FakeFetch(),
        synthesize_fn=synthesize,
        clock=lambda: 0.0,
        emit=lambda e: None,
    )
    assert count_distinct_domains(report.sources) == 2


def test_should_allow_finish() -> None:
    a = Source(url="https://a.com/1", content="", fetched_at=0.0)
    results = [SearchResult(title="t", url="https://b.com/x", snippet="s")]
    # Not enough domains, and a new domain is available -> must NOT finish yet.
    assert should_allow_finish([a], results, min_domains=2) is False
    # Enough domains -> allowed.
    assert should_allow_finish([a], results, min_domains=1) is True
    # Not enough domains but no new domain available -> allowed (avoid spinning).
    assert should_allow_finish([a], [], min_domains=2) is True


def test_should_allow_finish_after_direct_weather_result() -> None:
    weather = Source(url="https://wttr.in/Hanoi?format=3", content="Hanoi: +33°C", fetched_at=0.0)
    extra = [SearchResult(title="Other", url="https://example.com/weather", snippet="")]

    assert should_allow_finish([weather], extra, min_domains=2) is True


def test_run_session_caps_per_domain() -> None:
    llm = ScriptedLLM(
        decisions=[
            {"action": "search", "query": "topic"},
            {"action": "read", "url": "https://a.com/1"},
            {"action": "read", "url": "https://a.com/2"},  # same domain -> capped
            {"action": "read", "url": "https://b.com/1"},
            {"action": "finish"},
        ]
    )
    report = run_session(
        question="q",
        settings=_settings(max_per_domain=1, min_domains=1),
        llm=llm,
        search=FakeSearch(
            SearchOutcome(
                results=(
                    SearchResult(title="A", url="https://a.com/1", snippet=""),
                    SearchResult(title="B", url="https://a.com/2", snippet=""),
                    SearchResult(title="C", url="https://b.com/1", snippet=""),
                )
            )
        ),
        fetch=FakeFetch(),
        synthesize_fn=synthesize,
        clock=lambda: 0.0,
        emit=lambda e: None,
    )
    hosts = sorted({s.url for s in report.sources})
    assert hosts == ["https://a.com/1", "https://b.com/1"]


def test_run_session_overrides_premature_finish() -> None:
    # LLM searches (finds two domains), then tries to finish with 0 sources.
    # The soft constraint should force it to keep reading until 2 domains.
    llm = ScriptedLLM(
        decisions=[
            {"action": "search", "query": "topic"},
            {"action": "finish"},  # premature: 0 domains, new ones available -> overridden
            {"action": "read", "url": "https://a.com/x"},
            {"action": "read", "url": "https://b.com/y"},
            {"action": "finish"},  # now 2 domains -> allowed
        ]
    )
    search = FakeSearch(
        SearchOutcome(
            results=(
                SearchResult(title="A", url="https://a.com/x", snippet="s"),
                SearchResult(title="B", url="https://b.com/y", snippet="s"),
            )
        )
    )
    report = run_session(
        question="q",
        settings=_settings(min_domains=2),
        llm=llm,
        search=search,
        fetch=FakeFetch(),
        synthesize_fn=synthesize,
        clock=lambda: 0.0,
        emit=lambda e: None,
    )
    assert count_distinct_domains(report.sources) == 2
