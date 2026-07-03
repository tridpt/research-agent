"""Tests for HttpFetchTool covering blocklist, redirects, and error branches.

A fake httpx client is injected so redirect-following, status handling, and
content extraction run without any network.
"""
from __future__ import annotations

import httpx

from research_agent.fetch_tool import FetchOutcome, HttpFetchTool, default_extractor


class _FakeResponse:
    def __init__(self, status_code=200, text="", headers=None, url="https://a.com") -> None:
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.url = httpx.URL(url)

    @property
    def is_redirect(self) -> bool:
        return self.status_code in (301, 302, 303, 307, 308)


class _FakeClient:
    """Returns queued responses keyed by call order."""

    def __init__(self, responses) -> None:
        self._responses = list(responses)
        self.gets: list[str] = []

    def get(self, url):
        self.gets.append(url)
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


def _tool(responses, *, blocked=frozenset(), validator=lambda u: None, max_redirects=5):
    tool = HttpFetchTool(
        blocked_domains=blocked,
        per_source_char_limit=1000,
        extractor=lambda html: html,  # identity so we can assert on content
        clock=lambda: 123.0,
        url_validator=validator,
        max_redirects=max_redirects,
    )
    tool._client = _FakeClient(responses)
    return tool


# --------------------------------------------------------------------------
# default_extractor
# --------------------------------------------------------------------------
def test_default_extractor_falls_back_to_raw_when_no_extraction() -> None:
    # Non-HTML garbage yields no trafilatura extraction; falls back to raw text.
    raw = "plain text with no html structure"
    assert default_extractor(raw) == raw


# --------------------------------------------------------------------------
# Blocklist / URL validation
# --------------------------------------------------------------------------
def test_fetch_blocks_listed_domain_before_network() -> None:
    tool = _tool([], blocked=frozenset({"evil.com"}))
    outcome = tool.fetch("https://evil.com/x")
    assert outcome.blocked is True
    assert "blocked domain" in outcome.error
    assert tool._client.gets == []  # no network call


def test_fetch_rejects_unsafe_url() -> None:
    tool = _tool([], validator=lambda u: "loopback address")
    outcome = tool.fetch("http://127.0.0.1/x")
    assert not outcome.ok
    assert "unsafe URL" in outcome.error


# --------------------------------------------------------------------------
# Happy path
# --------------------------------------------------------------------------
def test_fetch_returns_source_on_success() -> None:
    tool = _tool([_FakeResponse(status_code=200, text="hello world", url="https://a.com/p")])
    outcome = tool.fetch("https://a.com/p")
    assert outcome.ok
    assert outcome.source.content == "hello world"
    assert outcome.source.url == "https://a.com/p"
    assert outcome.source.fetched_at == 123.0


def test_fetch_http_error_status() -> None:
    tool = _tool([_FakeResponse(status_code=404, url="https://a.com/missing")])
    outcome = tool.fetch("https://a.com/missing")
    assert not outcome.ok
    assert "HTTP 404" in outcome.error


# --------------------------------------------------------------------------
# Redirects
# --------------------------------------------------------------------------
def test_fetch_follows_redirect_then_succeeds() -> None:
    redirect = _FakeResponse(status_code=302, headers={"Location": "https://a.com/final"}, url="https://a.com/start")
    final = _FakeResponse(status_code=200, text="final content", url="https://a.com/final")
    tool = _tool([redirect, final])
    outcome = tool.fetch("https://a.com/start")
    assert outcome.ok
    assert outcome.source.content == "final content"


def test_fetch_redirect_without_location_errors() -> None:
    tool = _tool([_FakeResponse(status_code=302, headers={}, url="https://a.com/start")])
    outcome = tool.fetch("https://a.com/start")
    assert not outcome.ok
    assert "redirect without Location" in outcome.error


def test_fetch_too_many_redirects() -> None:
    # Every response is a redirect; exceeding max_redirects errors out.
    loop = [
        _FakeResponse(status_code=302, headers={"Location": f"https://a.com/{i}"}, url=f"https://a.com/{i}")
        for i in range(5)
    ]
    tool = _tool(loop, max_redirects=2)
    outcome = tool.fetch("https://a.com/0")
    assert not outcome.ok
    assert "too many redirects" in outcome.error


def test_fetch_blocks_redirect_to_blocked_domain() -> None:
    redirect = _FakeResponse(status_code=302, headers={"Location": "https://evil.com/x"}, url="https://a.com/start")
    tool = _tool([redirect], blocked=frozenset({"evil.com"}))
    outcome = tool.fetch("https://a.com/start")
    assert outcome.blocked is True
    assert "blocked redirect domain" in outcome.error


def test_fetch_blocks_unsafe_redirect_url() -> None:
    redirect = _FakeResponse(status_code=302, headers={"Location": "http://169.254.0.1/x"}, url="https://a.com/start")

    def validator(url):
        return "link-local" if "169.254" in url else None

    tool = _tool([redirect], validator=validator)
    outcome = tool.fetch("https://a.com/start")
    assert not outcome.ok
    assert "unsafe redirect URL" in outcome.error


# --------------------------------------------------------------------------
# Network failure
# --------------------------------------------------------------------------
def test_fetch_network_error_is_captured() -> None:
    tool = _tool([httpx.ConnectError("no route")])
    outcome = tool.fetch("https://a.com/x")
    assert isinstance(outcome, FetchOutcome)
    assert not outcome.ok
    assert "fetch failed" in outcome.error
