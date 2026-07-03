"""Tests for the OpenAI-compatible LLM client and its recovery helpers.

The provider lazily creates an ``httpx.Client``; we inject a fake client so the
real request-building and response-parsing code runs without any network.
"""
from __future__ import annotations

import json

import httpx
import pytest

from research_agent.errors import LLMError
from research_agent.llm import (
    Message,
    OpenAICompatibleProvider,
    TransientLLMError,
    _recover_from_failed_generation,
    is_transient_status,
    parse_retry_after,
    parse_retry_after_from_body,
)


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------
def test_is_transient_status() -> None:
    assert is_transient_status(429)
    assert is_transient_status(503)
    assert not is_transient_status(400)
    assert not is_transient_status(200)


def test_parse_retry_after_numeric_and_clamped() -> None:
    assert parse_retry_after("5") == 5.0
    assert parse_retry_after("-3") == 0.0
    assert parse_retry_after(None) is None
    assert parse_retry_after("not-a-date") is None


def test_parse_retry_after_http_date() -> None:
    # A date far in the past clamps to 0; a valid future date is positive.
    assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0


def test_parse_retry_after_from_body_variants() -> None:
    assert parse_retry_after_from_body("Please retry in 7.5s") == 7.5
    assert parse_retry_after_from_body("retry after 30 seconds") == 30.0
    assert parse_retry_after_from_body("retry in 500 ms") == 0.5
    assert parse_retry_after_from_body("no hint here") is None
    assert parse_retry_after_from_body(None) is None


def test_recover_from_function_call_text() -> None:
    decision = _recover_from_failed_generation('<function=search{"query": "cats"}>')
    assert decision == {"action": "search", "query": "cats"}


def test_recover_from_plain_json() -> None:
    decision = _recover_from_failed_generation('{"action": "read", "url": "https://a.com"}')
    assert decision == {"action": "read", "url": "https://a.com"}


def test_recover_from_error_body_failed_generation() -> None:
    body = json.dumps({"error": {"failed_generation": '{"action": "finish"}'}})
    assert _recover_from_failed_generation(body) == {"action": "finish"}


def test_recover_returns_none_for_garbage() -> None:
    assert _recover_from_failed_generation("just some prose") is None
    assert _recover_from_failed_generation("") is None


# --------------------------------------------------------------------------
# OpenAICompatibleProvider with an injected fake httpx client
# --------------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="", headers=None) -> None:
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._json


class _FakeClient:
    """Captures the last POST payload and returns queued responses."""

    def __init__(self, responses) -> None:
        self._responses = list(responses)
        self.posts: list[dict] = []

    def post(self, path, json=None):
        self.posts.append({"path": path, "json": json})
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


def _provider(responses):
    """Build a provider, then swap in a fake client (skips real httpx setup)."""
    p = OpenAICompatibleProvider(api_key="k", base_url="https://x/v1", model="m")
    p._client = _FakeClient(responses)
    return p


def test_generate_returns_message_content() -> None:
    resp = _FakeResponse(json_data={"choices": [{"message": {"content": "hello"}}]})
    p = _provider([resp])
    assert p.generate([Message(role="user", content="hi")]) == "hello"


def test_decide_action_reads_tool_call() -> None:
    resp = _FakeResponse(json_data={"choices": [{"message": {
        "tool_calls": [{"function": {"name": "search", "arguments": '{"query": "q"}'}}]
    }}]})
    p = _provider([resp])
    decision = p.decide_action([Message(role="user", content="hi")], tools=[])
    assert decision == {"action": "search", "query": "q"}


def test_decide_action_recovers_from_plain_content() -> None:
    resp = _FakeResponse(json_data={"choices": [{"message": {
        "content": '{"action": "finish"}', "tool_calls": []
    }}]})
    p = _provider([resp])
    assert p.decide_action([Message(role="user", content="hi")], tools=[]) == {"action": "finish"}


def test_decide_action_no_tool_call_sentinel() -> None:
    resp = _FakeResponse(json_data={"choices": [{"message": {"content": "just prose"}}]})
    p = _provider([resp])
    decision = p.decide_action([Message(role="user", content="hi")], tools=[])
    assert decision["action"] == "__no_tool_call__"


def test_decide_action_recovers_from_error_body() -> None:
    body = json.dumps({"error": {"failed_generation": '{"action": "read", "url": "https://a.com"}'}})
    resp = _FakeResponse(status_code=400, text=body)
    p = _provider([resp])
    decision = p.decide_action([Message(role="user", content="hi")], tools=[])
    assert decision == {"action": "read", "url": "https://a.com"}


def test_transient_status_raises_with_retry_after_header() -> None:
    resp = _FakeResponse(status_code=429, headers={"Retry-After": "12"})
    p = _provider([resp])
    with pytest.raises(TransientLLMError) as exc:
        p.generate([Message(role="user", content="hi")])
    assert exc.value.retry_after == 12.0


def test_transient_status_uses_body_hint() -> None:
    resp = _FakeResponse(status_code=503, text="Please retry in 3s")
    p = _provider([resp])
    with pytest.raises(TransientLLMError) as exc:
        p.generate([Message(role="user", content="hi")])
    assert exc.value.retry_after == 3.0


def test_fatal_http_error_raises_llm_error() -> None:
    resp = _FakeResponse(status_code=401, text="unauthorized")
    p = _provider([resp])
    with pytest.raises(LLMError):
        p.generate([Message(role="user", content="hi")])


def test_timeout_becomes_transient_error() -> None:
    p = _provider([httpx.TimeoutException("slow")])
    with pytest.raises(TransientLLMError):
        p.generate([Message(role="user", content="hi")])


def test_connection_error_becomes_transient_error() -> None:
    p = _provider([httpx.ConnectError("down")])
    with pytest.raises(TransientLLMError):
        p.generate([Message(role="user", content="hi")])


# --------------------------------------------------------------------------
# Streaming (generate_stream) with an injected fake client
# --------------------------------------------------------------------------
class _FakeStreamResponse:
    def __init__(self, lines, status_code=200, headers=None, body=b"") -> None:
        self._lines = lines
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def iter_lines(self):
        yield from self._lines

    def read(self):
        return self._body


class _StreamClient:
    def __init__(self, response) -> None:
        self._response = response
        self.calls: list[dict] = []

    def stream(self, method, path, json=None):
        self.calls.append({"method": method, "path": path, "json": json})
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _stream_provider(response):
    p = OpenAICompatibleProvider(api_key="k", base_url="https://x/v1", model="m")
    p._client = _StreamClient(response)
    return p


def test_generate_stream_yields_content_pieces() -> None:
    lines = [
        'data: {"choices": [{"delta": {"content": "Hel"}}]}',
        'data: {"choices": [{"delta": {"content": "lo"}}]}',
        "",  # blank line ignored
        "data: [DONE]",
    ]
    p = _stream_provider(_FakeStreamResponse(lines))
    assert "".join(p.generate_stream([Message(role="user", content="hi")])) == "Hello"


def test_generate_stream_transient_status_raises() -> None:
    p = _stream_provider(
        _FakeStreamResponse([], status_code=429, headers={"Retry-After": "4"}, body=b"slow")
    )
    with pytest.raises(TransientLLMError) as exc:
        list(p.generate_stream([Message(role="user", content="hi")]))
    assert exc.value.retry_after == 4.0


def test_generate_stream_fatal_status_raises() -> None:
    p = _stream_provider(_FakeStreamResponse([], status_code=400, body=b"bad request"))
    with pytest.raises(LLMError):
        list(p.generate_stream([Message(role="user", content="hi")]))
