"""Coverage for the network I/O branches of the external info tools.

Each tool lazily imports httpx, so patching ``httpx.get`` exercises the real
``fetch_*`` code path (request building + response parsing) without hitting the
network. Error paths raise the tool's own exception type.
"""
from __future__ import annotations

import httpx
import pytest

from research_agent.arxiv import ArxivError, fetch_arxiv
from research_agent.convert import ConvertError, convert, fetch_currency
from research_agent.github import GitHubError, fetch_github
from research_agent.news import NewsError, fetch_news
from research_agent.stock import StockError, fetch_stock_quote
from research_agent.weather import WeatherError, fetch_weather
from research_agent.wikipedia import WikipediaError, fetch_wikipedia

_ARXIV_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2005.11401</id>
    <published>2020-05-22T00:00:00Z</published>
    <title>RAG paper</title>
    <summary>An abstract.</summary>
    <author><name>A. Author</name></author>
  </entry>
</feed>"""


class FakeResponse:
    def __init__(self, *, text: str = "", json_data: object = None, status_code: int = 200) -> None:
        self.text = text
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)  # type: ignore[arg-type]

    def json(self) -> object:
        return self._json


def _route(url: str) -> FakeResponse:
    if "wttr.in" in url:
        return FakeResponse(text="Hanoi: +33C")
    if "finance.yahoo.com" in url:
        return FakeResponse(json_data={"chart": {"result": [{"meta": {
            "symbol": "AAPL", "regularMarketPrice": 207.49, "currency": "USD",
        }}], "error": None}})
    if "wikipedia.org" in url:
        return FakeResponse(json_data={"query": {"pages": {"1": {
            "index": 1, "title": "CAP theorem", "extract": "A theorem.",
            "fullurl": "https://en.wikipedia.org/wiki/CAP_theorem",
        }}}})
    if "arxiv.org" in url:
        return FakeResponse(text=_ARXIV_XML)
    if "hn.algolia.com" in url:
        return FakeResponse(json_data={"hits": [{
            "title": "Story", "url": "https://e.com", "points": 5,
            "num_comments": 1, "created_at": "2026-01-01T00:00:00Z", "objectID": "1",
        }]})
    if "frankfurter" in url:
        return FakeResponse(json_data={"amount": 100.0, "base": "USD", "rates": {"EUR": 88.0}})
    if url.endswith("/releases/latest"):
        return FakeResponse(json_data={"tag_name": "v1.0", "published_at": "2024-01-01T00:00:00Z"})
    if "api.github.com/repos/" in url:
        return FakeResponse(json_data={
            "full_name": "o/r", "description": "d", "stargazers_count": 9,
            "forks_count": 1, "open_issues_count": 0, "language": "Python",
            "license": {"spdx_id": "MIT"}, "html_url": "https://github.com/o/r",
        })
    raise AssertionError(f"unexpected url {url}")


@pytest.fixture
def routed_httpx(monkeypatch):
    monkeypatch.setattr("httpx.get", lambda url, **kw: _route(url))


def test_fetch_weather(routed_httpx) -> None:
    url, content = fetch_weather("Hanoi")
    assert url.startswith("https://wttr.in/")
    assert content == "Weather for 'Hanoi': Hanoi: +33C"


def test_fetch_stock(routed_httpx) -> None:
    url, summary = fetch_stock_quote("AAPL")
    assert "finance.yahoo.com" in url
    assert "AAPL" in summary and "207.49 USD" in summary


def test_fetch_wikipedia(routed_httpx) -> None:
    url, content = fetch_wikipedia("CAP theorem")
    assert url.endswith("/CAP_theorem")
    assert "Wikipedia — CAP theorem" in content


def test_fetch_arxiv(routed_httpx) -> None:
    url, content = fetch_arxiv("RAG")
    assert "2005.11401" in url
    assert "RAG paper" in content


def test_fetch_news(routed_httpx) -> None:
    url, content = fetch_news("ai")
    assert "hn.algolia.com" in url
    assert "Story" in content


def test_fetch_github_with_release(routed_httpx) -> None:
    url, content = fetch_github("o/r")
    assert url == "https://github.com/o/r"
    assert "GitHub — o/r" in content
    assert "Latest release: v1.0" in content


def test_fetch_currency_via_convert(routed_httpx) -> None:
    assert convert("100 USD to EUR") == "100 USD = 88 EUR"
    assert fetch_currency(100.0, "usd", "eur") == 88.0


def test_fetch_error_paths_raise_tool_errors(monkeypatch) -> None:
    def boom(url, **kw):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr("httpx.get", boom)
    with pytest.raises(WeatherError):
        fetch_weather("Hanoi")
    with pytest.raises(StockError):
        fetch_stock_quote("AAPL")
    with pytest.raises(WikipediaError):
        fetch_wikipedia("x")
    with pytest.raises(ArxivError):
        fetch_arxiv("x")
    with pytest.raises(NewsError):
        fetch_news("x")
    with pytest.raises(GitHubError):
        fetch_github("o/r")
    with pytest.raises(ConvertError):
        fetch_currency(1.0, "usd", "eur")


def test_run_session_dispatches_registry_tool_as_source(routed_httpx) -> None:
    """The generic info-tool branch records a fetched Source end to end."""
    from research_agent.agent import run_session
    from research_agent.config import ENV_API_KEY, resolve_settings
    from research_agent.synthesizer import synthesize

    from .fakes import FakeFetch, FakeSearch, ScriptedLLM

    llm = ScriptedLLM(
        decisions=[
            {"action": "get_github", "repo": "o/r"},
            {"action": "finish"},
        ],
        text="A report about the repo [1].",
    )
    settings = resolve_settings(env={ENV_API_KEY: "k"}, cli_overrides={"max_rounds": 5})
    report = run_session(
        question="Tell me about o/r",
        settings=settings,
        llm=llm,
        search=FakeSearch(),
        fetch=FakeFetch(),
        synthesize_fn=synthesize,
        clock=lambda: 0.0,
        emit=lambda e: None,
    )
    assert any(s.url == "https://github.com/o/r" for s in report.sources)


def test_run_session_emits_error_when_registry_tool_fails(monkeypatch) -> None:
    """A failing info-tool fetch is reported, not fatal."""
    from research_agent.agent import run_session
    from research_agent.config import ENV_API_KEY, resolve_settings
    from research_agent.models import TraceEventType
    from research_agent.synthesizer import synthesize

    from .fakes import FakeFetch, FakeSearch, ScriptedLLM

    monkeypatch.setattr("httpx.get", lambda url, **kw: (_ for _ in ()).throw(httpx.ConnectError("x")))
    events: list[str] = []
    llm = ScriptedLLM(
        decisions=[{"action": "get_github", "repo": "o/r"}, {"action": "finish"}],
        text="No data.",
    )
    settings = resolve_settings(env={ENV_API_KEY: "k"}, cli_overrides={"max_rounds": 5})
    run_session(
        question="q",
        settings=settings,
        llm=llm,
        search=FakeSearch(),
        fetch=FakeFetch(),
        synthesize_fn=synthesize,
        clock=lambda: 0.0,
        emit=lambda e: events.append(e.detail.get("error", "")) if e.type is TraceEventType.TOOL_ERROR else None,
    )
    assert any("get_github error" in e for e in events)
