"""Tests for parallel prefetching (pure selection + concurrent warming)."""
from __future__ import annotations

from research_agent.models import SearchResult, Source
from research_agent.prefetch import prefetch_urls, select_prefetch_urls

from .fakes import FakeFetch


def _results(*urls: str) -> list[SearchResult]:
    return [SearchResult(title=u, url=u, snippet="") for u in urls]


def test_select_prefetch_urls_picks_unread_top_n() -> None:
    results = _results("https://a.com/1", "https://b.com/1", "https://c.com/1")
    chosen = select_prefetch_urls([], results, max_per_domain=2, limit=2)
    assert chosen == ("https://a.com/1", "https://b.com/1")


def test_select_prefetch_urls_skips_read_and_excluded() -> None:
    read = [Source(url="https://a.com/1", content="", fetched_at=0.0)]
    results = _results("https://a.com/1", "https://b.com/1", "https://c.com/1")
    chosen = select_prefetch_urls(
        read, results, max_per_domain=2, limit=5, exclude_urls={"https://b.com/1"}
    )
    assert chosen == ("https://c.com/1",)


def test_select_prefetch_urls_respects_per_domain_cap() -> None:
    results = _results("https://a.com/1", "https://a.com/2", "https://b.com/1")
    chosen = select_prefetch_urls([], results, max_per_domain=1, limit=5)
    assert chosen == ("https://a.com/1", "https://b.com/1")


def test_select_prefetch_urls_zero_limit() -> None:
    assert select_prefetch_urls([], _results("https://a.com"), 2, 0) == ()


def test_prefetch_urls_warms_each_url_once() -> None:
    fetch = FakeFetch()
    n = prefetch_urls(fetch, ["https://a.com", "https://b.com", "https://a.com"])
    assert n == 2  # deduped
    assert sorted(fetch.urls) == ["https://a.com", "https://b.com"]


def test_prefetch_urls_empty() -> None:
    fetch = FakeFetch()
    assert prefetch_urls(fetch, []) == 0
    assert fetch.urls == []
