"""Tests for the search providers and the fallback chain.

Each HTTP-backed provider lazily creates an ``httpx.Client``; we swap in a fake
client so request-building and response-parsing run without any network.
"""
from __future__ import annotations

import httpx

from research_agent.models import SearchResult
from research_agent.search_tool import (
    DuckDuckGoSearchTool,
    FallbackSearchTool,
    HttpSearchTool,
    SearchOutcome,
    TavilySearchTool,
    parse_search_results,
)


# --------------------------------------------------------------------------
# parse_search_results (pure)
# --------------------------------------------------------------------------
def test_parse_search_results_from_results_key() -> None:
    payload = {"results": [
        {"title": "T", "url": "https://a.gov/x", "snippet": "s"},
        {"name": "N", "link": "https://b.com/y", "description": "d"},
    ]}
    results = parse_search_results(payload)
    urls = {r.url for r in results}
    assert urls == {"https://a.gov/x", "https://b.com/y"}


def test_parse_search_results_skips_items_without_url() -> None:
    payload = [{"title": "no url"}, {"url": "https://a.com"}, "not-a-dict"]
    results = parse_search_results(payload)
    assert [r.url for r in results] == ["https://a.com"]


def test_parse_search_results_handles_unexpected_shape() -> None:
    assert parse_search_results(None) == ()
    assert parse_search_results(42) == ()


# --------------------------------------------------------------------------
# Fake client helpers
# --------------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, status_code=200, json_data=None) -> None:
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json


class _FakeGetClient:
    def __init__(self, response) -> None:
        self._response = response
        self.calls: list[dict] = []

    def get(self, endpoint, params=None):
        self.calls.append({"endpoint": endpoint, "params": params})
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class _FakePostClient:
    def __init__(self, response) -> None:
        self._response = response
        self.calls: list[dict] = []

    def post(self, endpoint, json=None):
        self.calls.append({"endpoint": endpoint, "json": json})
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


# --------------------------------------------------------------------------
# HttpSearchTool
# --------------------------------------------------------------------------
def test_http_search_returns_results() -> None:
    tool = HttpSearchTool(endpoint="https://search/api", api_key="k")
    tool._client = _FakeGetClient(_FakeResponse(json_data={"results": [
        {"title": "T", "url": "https://a.com", "snippet": "s"}
    ]}))
    outcome = tool.search("q")
    assert outcome.ok
    assert outcome.results[0].url == "https://a.com"


def test_http_search_http_error_status() -> None:
    tool = HttpSearchTool(endpoint="https://search/api")
    tool._client = _FakeGetClient(_FakeResponse(status_code=500))
    outcome = tool.search("q")
    assert not outcome.ok
    assert "500" in outcome.error


def test_http_search_network_error() -> None:
    tool = HttpSearchTool(endpoint="https://search/api")
    tool._client = _FakeGetClient(httpx.ConnectError("down"))
    outcome = tool.search("q")
    assert "search failed" in outcome.error


def test_http_search_invalid_json() -> None:
    class _BadJson(_FakeResponse):
        def json(self):
            raise ValueError("bad json")

    tool = HttpSearchTool(endpoint="https://search/api")
    tool._client = _FakeGetClient(_BadJson())
    outcome = tool.search("q")
    assert "invalid JSON" in outcome.error


# --------------------------------------------------------------------------
# TavilySearchTool
# --------------------------------------------------------------------------
def test_tavily_search_returns_results() -> None:
    tool = TavilySearchTool(api_key="k")
    tool._client = _FakePostClient(_FakeResponse(json_data={"results": [
        {"title": "T", "url": "https://a.com", "snippet": "s"}
    ]}))
    outcome = tool.search("q")
    assert outcome.ok and outcome.results[0].url == "https://a.com"


def test_tavily_search_http_error() -> None:
    tool = TavilySearchTool(api_key="k")
    tool._client = _FakePostClient(_FakeResponse(status_code=429))
    outcome = tool.search("q")
    assert "tavily HTTP 429" in outcome.error


def test_tavily_search_network_error() -> None:
    tool = TavilySearchTool(api_key="k")
    tool._client = _FakePostClient(httpx.ConnectError("down"))
    outcome = tool.search("q")
    assert "tavily search failed" in outcome.error


# --------------------------------------------------------------------------
# DuckDuckGoSearchTool (injected searcher, no network)
# --------------------------------------------------------------------------
def test_ddg_search_uses_injected_searcher() -> None:
    def fake_searcher(query, max_results, region):
        return [{"title": "T", "href": "https://a.com", "body": "s"}]

    tool = DuckDuckGoSearchTool(searcher=fake_searcher)
    outcome = tool.search("q")
    assert outcome.ok and outcome.results[0].url == "https://a.com"


def test_ddg_search_recovers_from_provider_error() -> None:
    def boom(query, max_results, region):
        raise RuntimeError("rate limited")

    tool = DuckDuckGoSearchTool(searcher=boom)
    outcome = tool.search("q")
    assert not outcome.ok
    assert "duckduckgo search failed" in outcome.error


# --------------------------------------------------------------------------
# FallbackSearchTool
# --------------------------------------------------------------------------
class _StubProvider:
    def __init__(self, outcome) -> None:
        self._outcome = outcome
        self.called = False

    def search(self, query):
        self.called = True
        return self._outcome


def test_fallback_requires_at_least_one_provider() -> None:
    import pytest

    with pytest.raises(ValueError):
        FallbackSearchTool([])


def test_fallback_returns_first_provider_with_results() -> None:
    good = _StubProvider(SearchOutcome(results=(SearchResult("T", "https://a.com", "s"),)))
    never = _StubProvider(SearchOutcome(results=(SearchResult("T", "https://b.com", "s"),)))
    tool = FallbackSearchTool([good, never])
    outcome = tool.search("q")
    assert outcome.results[0].url == "https://a.com"
    assert never.called is False


def test_fallback_skips_empty_and_errored_providers() -> None:
    empty = _StubProvider(SearchOutcome(results=()))
    errored = _StubProvider(SearchOutcome(error="boom"))
    good = _StubProvider(SearchOutcome(results=(SearchResult("T", "https://c.com", "s"),)))
    tool = FallbackSearchTool([empty, errored, good])
    outcome = tool.search("q")
    assert outcome.results[0].url == "https://c.com"


def test_fallback_combines_errors_when_all_fail() -> None:
    tool = FallbackSearchTool([
        _StubProvider(SearchOutcome(error="e1")),
        _StubProvider(SearchOutcome(error="e2")),
    ])
    outcome = tool.search("q")
    assert not outcome.ok
    assert "e1" in outcome.error and "e2" in outcome.error
