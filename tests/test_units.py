"""Example/boundary/error unit tests covering acceptance criteria."""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from research_agent.agent import run_session
from research_agent.cli import read_question
from research_agent.config import ENV_API_KEY, resolve_settings
from research_agent.decision import parse_decision
from research_agent.errors import ConfigError, LLMError, ReportWriteError
from research_agent.llm import TransientLLMError
from research_agent.models import (
    ActionType,
    AgentDecision,
    InvalidDecision,
    SearchResult,
    Settings,
    Source,
    TraceEvent,
    TraceEventType,
)
from research_agent.observability import render_trace
from research_agent.report_writer import write_report
from research_agent.retry import call_with_retry
from research_agent.search_tool import (
    DuckDuckGoSearchTool,
    SearchOutcome,
    parse_search_results,
)
from research_agent.synthesizer import synthesize

from .fakes import FakeFetch, FakeSearch, ScriptedLLM


# ---- CLI input (R1.1, R1.2) ----
def test_question_from_args() -> None:
    ns = argparse.Namespace(question="what is rust")
    assert read_question(ns, lambda: "unused") == "what is rust"


def test_question_prompts_when_missing() -> None:
    ns = argparse.Namespace(question=None)
    answers = iter(["   ", "", "real question"])
    assert read_question(ns, lambda: next(answers)) == "real question"


# ---- Config (R8.1, R8.3, R9.1) ----
def test_config_reads_api_key_from_env() -> None:
    s = resolve_settings(env={ENV_API_KEY: "secret"}, cli_overrides={})
    assert s.api_key == "secret"


def test_config_missing_key_raises() -> None:
    with pytest.raises(ConfigError):
        resolve_settings(env={}, cli_overrides={})


def test_config_loads_budget() -> None:
    s = resolve_settings(env={ENV_API_KEY: "k"}, cli_overrides={"max_sources": 3})
    assert s.budget.max_sources == 3


# ---- parse_decision (R11.3) ----
def test_parse_decision_valid_search() -> None:
    d = parse_decision({"action": "search", "query": "x"})
    assert isinstance(d, AgentDecision) and d.action is ActionType.SEARCH


def test_parse_decision_invalid_missing_query() -> None:
    assert isinstance(parse_decision({"action": "search"}), InvalidDecision)


def test_parse_decision_unknown_action() -> None:
    assert isinstance(parse_decision({"action": "fly"}), InvalidDecision)


def test_parse_decision_calculate() -> None:
    d = parse_decision({"action": "calculate", "expression": "1+1"})
    assert isinstance(d, AgentDecision)
    assert d.action is ActionType.CALCULATE and d.expression == "1+1"


def test_parse_decision_calculate_missing_expr() -> None:
    assert isinstance(parse_decision({"action": "calculate"}), InvalidDecision)


def test_parse_decision_now() -> None:
    d = parse_decision({"action": "now"})
    assert isinstance(d, AgentDecision) and d.action is ActionType.NOW


# ---- tool-call recovery from malformed output (Groq/Llama quirk) ----
def test_recover_from_function_tag() -> None:
    from research_agent.llm import _recover_from_failed_generation

    rec = _recover_from_failed_generation('<function=search{"query": "CAP theorem"}>')
    assert rec == {"action": "search", "query": "CAP theorem"}


def test_recover_from_json_blob() -> None:
    from research_agent.llm import _recover_from_failed_generation

    rec = _recover_from_failed_generation('some text {"action": "read", "url": "https://a.com"} tail')
    assert rec == {"action": "read", "url": "https://a.com"}


def test_recover_returns_none_when_nothing() -> None:
    from research_agent.llm import _recover_from_failed_generation

    assert _recover_from_failed_generation("just prose, no action") is None
    assert _recover_from_failed_generation("") is None


def test_recover_from_error_body_with_wrapper() -> None:
    from research_agent.llm import _recover_from_failed_generation

    # Mimics a Groq 400 body where the model called a tool named "JSON" and
    # nested the real decision inside arguments.
    body = (
        '{"error":{"message":"Tool call validation failed",'
        '"code":"tool_use_failed",'
        '"failed_generation":"{\\"name\\": \\"JSON\\", \\"arguments\\": '
        '{\\"action\\":\\"read\\",\\"url\\":\\"https://en.wikipedia.org/wiki/CAP_theorem\\"}}"}}'
    )
    rec = _recover_from_failed_generation(body)
    assert rec == {"action": "read", "url": "https://en.wikipedia.org/wiki/CAP_theorem"}


def test_recover_from_named_tool_arguments() -> None:
    from research_agent.llm import _recover_from_failed_generation

    # {"name": "search", "arguments": {"query": "..."}} -> action=search
    rec = _recover_from_failed_generation('{"name": "search", "arguments": {"query": "cats"}}')
    assert rec == {"action": "search", "query": "cats"}


# ---- retry hint parsed from error body (Gemini quirk) ----
def test_parse_retry_after_from_body_seconds() -> None:
    from research_agent.llm import parse_retry_after_from_body

    assert parse_retry_after_from_body("Please retry in 7.92s") == 7.92
    assert parse_retry_after_from_body("retry after 30 seconds") == 30.0
    assert parse_retry_after_from_body("retry in 500ms") == 0.5


def test_parse_retry_after_from_body_none() -> None:
    from research_agent.llm import parse_retry_after_from_body

    assert parse_retry_after_from_body("some unrelated error") is None
    assert parse_retry_after_from_body(None) is None


# ---- Search parsing (R3.1, R3.3) ----
def test_parse_search_results() -> None:
    payload = {"results": [{"title": "T", "url": "https://a.com", "snippet": "s"}]}
    out = parse_search_results(payload)
    assert len(out) == 1 and out[0].url == "https://a.com"


def test_search_empty_is_ok() -> None:
    assert parse_search_results({"results": []}) == ()


# ---- Fallback search (R5.5) ----
def test_fallback_uses_second_when_first_empty() -> None:
    from research_agent.models import SearchResult
    from research_agent.search_tool import FallbackSearchTool

    class Empty:
        def search(self, q):
            return SearchOutcome(results=())

    class Works:
        def search(self, q):
            return SearchOutcome(results=(SearchResult("t", "https://x.com", "s"),))

    tool = FallbackSearchTool([Empty(), Works()])
    out = tool.search("q")
    assert out.ok and out.results[0].url == "https://x.com"


def test_fallback_uses_second_when_first_errors() -> None:
    from research_agent.models import SearchResult
    from research_agent.search_tool import FallbackSearchTool

    class Boom:
        def search(self, q):
            return SearchOutcome(error="rate limited")

    class Works:
        def search(self, q):
            return SearchOutcome(results=(SearchResult("t", "https://y.com", "s"),))

    out = FallbackSearchTool([Boom(), Works()]).search("q")
    assert out.ok and out.results[0].url == "https://y.com"


def test_fallback_all_fail_returns_error() -> None:
    from research_agent.search_tool import FallbackSearchTool

    class Boom:
        def __init__(self, msg):
            self.msg = msg

        def search(self, q):
            return SearchOutcome(error=self.msg)

    out = FallbackSearchTool([Boom("a down"), Boom("b down")]).search("q")
    assert not out.ok
    assert "a down" in out.error and "b down" in out.error


def test_fallback_requires_provider() -> None:
    from research_agent.search_tool import FallbackSearchTool

    with pytest.raises(ValueError):
        FallbackSearchTool([])


# ---- DuckDuckGo search tool (R3.1, R3.4, R5.5) ----
def test_ddg_search_maps_results() -> None:
    def fake_searcher(query, max_results, region):
        return [
            {"title": "A", "href": "https://a.com", "body": "about a"},
            {"title": "B", "href": "https://b.com", "body": "about b"},
        ]

    tool = DuckDuckGoSearchTool(searcher=fake_searcher)
    outcome = tool.search("topic")
    assert outcome.ok
    assert [r.url for r in outcome.results] == ["https://a.com", "https://b.com"]
    assert outcome.results[0].snippet == "about a"


def test_ddg_search_error_is_recoverable() -> None:
    def boom(query, max_results, region):
        raise RuntimeError("rate limited")

    outcome = DuckDuckGoSearchTool(searcher=boom).search("x")
    assert not outcome.ok
    assert "duckduckgo search failed" in (outcome.error or "")


# ---- Agent loop (R2.1, R2.2, R3.3) ----
def _settings() -> Settings:
    return resolve_settings(env={ENV_API_KEY: "k"}, cli_overrides={"max_rounds": 5, "max_sources": 5})


def test_run_session_collects_sources_and_synthesizes() -> None:
    llm = ScriptedLLM(
        decisions=[
            {"action": "search", "query": "topic"},
            {"action": "read", "url": "https://a.com/x"},
            {"action": "finish"},
        ]
    )
    search = FakeSearch(
        SearchOutcome(results=(SearchResult(title="A", url="https://a.com/x", snippet=""),))
    )
    fetch = FakeFetch()
    report = run_session(
        question="q",
        settings=_settings(),
        llm=llm,
        search=search,
        fetch=fetch,
        synthesize_fn=synthesize,
        clock=lambda: 0.0,
        emit=lambda e: None,
    )
    assert llm.decide_calls >= 1
    assert search.queries == ["topic"]
    assert fetch.urls == ["https://a.com/x"]
    assert report.sources and report.sources[0].url == "https://a.com/x"


def test_run_session_continues_on_empty_search() -> None:
    llm = ScriptedLLM(decisions=[{"action": "search", "query": "x"}, {"action": "finish"}])
    report = run_session(
        question="q",
        settings=_settings(),
        llm=llm,
        search=FakeSearch(SearchOutcome(results=())),
        fetch=FakeFetch(),
        synthesize_fn=synthesize,
        clock=lambda: 0.0,
        emit=lambda e: None,
    )
    assert report.no_information is True  # no sources collected


def test_run_session_paces_with_delay() -> None:
    # With a configured round delay, the injectable sleep is called between rounds.
    sleeps: list[float] = []
    llm = ScriptedLLM(
        decisions=[
            {"action": "search", "query": "x"},
            {"action": "read", "url": "https://a.com/1"},
            {"action": "finish"},
        ]
    )
    settings = resolve_settings(
        env={ENV_API_KEY: "k"},
        cli_overrides={"max_rounds": 5, "max_sources": 5, "min_domains": 1, "round_delay_seconds": 2.0},
    )
    run_session(
        question="q",
        settings=settings,
        llm=llm,
        search=FakeSearch(
            SearchOutcome(results=(SearchResult(title="A", url="https://a.com/1", snippet=""),))
        ),
        fetch=FakeFetch(),
        synthesize_fn=synthesize,
        clock=lambda: 0.0,
        emit=lambda e: None,
        sleep=sleeps.append,
    )
    # At least one inter-round pause of the configured length happened.
    assert sleeps and all(s == 2.0 for s in sleeps)


def test_run_session_uses_calculate_tool() -> None:
    # The agent calls calculate, then finishes; the tool note is passed to synth.
    captured = {}

    def capturing_synth(q, srcs, llm, tool_notes):
        captured["question"] = q
        captured["tool_notes"] = tool_notes
        return synthesize(q, srcs, llm, tool_notes)

    llm = ScriptedLLM(
        decisions=[
            {"action": "calculate", "expression": "(120-90)/90*100"},
            {"action": "finish"},
        ]
    )
    report = run_session(
        question="growth rate?",
        settings=_settings(),
        llm=llm,
        search=FakeSearch(SearchOutcome(results=())),
        fetch=FakeFetch(),
        synthesize_fn=capturing_synth,
        clock=lambda: 0.0,
        emit=lambda e: None,
    )
    assert captured["question"] == "growth rate?"
    assert "calculate((120-90)/90*100)" in captured["tool_notes"][0]
    assert "33.3" in captured["tool_notes"][0]
    assert report.no_information is False


def test_run_session_rejects_unapproved_read_and_pdf_actions() -> None:
    events = []
    llm = ScriptedLLM(
        decisions=[
            {"action": "read", "url": "http://127.0.0.1:8501/admin"},
            {"action": "read_pdf", "path": "C:/private/secret.pdf"},
            {"action": "finish"},
        ]
    )
    fetch = FakeFetch()
    run_session(
        question="q",
        settings=_settings(),
        llm=llm,
        search=FakeSearch(),
        fetch=fetch,
        synthesize_fn=synthesize,
        clock=lambda: 0.0,
        emit=events.append,
    )

    assert fetch.urls == []
    errors = [event.detail.get("error", "") for event in events]
    assert any("not returned by the search tool" in error for error in errors)
    assert any("read_pdf blocked" in error for error in errors)


def test_run_session_uses_weather_tool_as_a_source(monkeypatch) -> None:
    """Weather data must reach synthesis, including locations with accents."""
    captured = {}

    class WeatherResponse:
        text = "Hà Nội: ☀️  +33°C"

        def raise_for_status(self) -> None:
            pass

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        return WeatherResponse()

    monkeypatch.setattr("research_agent.agent.httpx.get", fake_get)

    def capturing_synth(_question, sources, _llm, _tool_notes):
        captured["sources"] = list(sources)
        return synthesize(_question, sources, _llm, _tool_notes)

    llm = ScriptedLLM(
        decisions=[
            {"action": "get_weather", "location": "Hà Nội"},
            {"action": "finish"},
        ],
        text="Trời nắng [https://wttr.in/H%C3%A0%20N%E1%BB%99i?format=3]",
    )
    report = run_session(
        question="Thời tiết ở Hà Nội hôm nay thế nào?",
        settings=_settings(),
        llm=llm,
        search=FakeSearch(),
        fetch=FakeFetch(),
        synthesize_fn=capturing_synth,
        clock=lambda: 0.0,
        emit=lambda e: None,
    )

    assert captured["url"] == "https://wttr.in/H%C3%A0%20N%E1%BB%99i?format=3"
    assert captured["headers"] == {"User-Agent": "research-agent/0.1"}
    assert len(captured["sources"]) == 1
    assert captured["sources"][0].content == "Weather for 'Hà Nội': Hà Nội: ☀️  +33°C"
    assert report.no_information is False
    assert len(report.sources) == 1


# ---- Synthesizer (R6.1, R6.5) ----
def test_synthesize_no_sources() -> None:
    rep = synthesize("q", [], ScriptedLLM(decisions=[]))
    assert rep.no_information is True
    assert "No reliable information" in rep.body_markdown


def test_synthesize_no_sources_vietnamese() -> None:
    rep = synthesize("q", [], ScriptedLLM(decisions=[]), language="vi")
    assert rep.no_information is True
    assert "Không tìm thấy thông tin" in rep.body_markdown


def test_synthesize_language_adds_instruction() -> None:
    captured = {}

    class CapturingLLM:
        def decide_action(self, m, t):
            return {"action": "finish"}

        def generate(self, messages):
            captured["system"] = messages[0].content
            return "Báo cáo [https://a.com/x]"

    srcs = [Source(url="https://a.com/x", content="c", fetched_at=0.0)]
    synthesize("q", srcs, CapturingLLM(), language="vi")
    assert "Vietnamese" in captured["system"]


def test_synthesize_normalizes_nested_url_citations() -> None:
    url = "https://a.com/x"
    source = Source(url=url, content="c", fetched_at=0.0)
    report = synthesize("q", [source], ScriptedLLM(decisions=[], text=f"Fact [[{url}]({url})]"))

    assert report.body_markdown == "Fact [1]"
    assert report.citations and report.citations[0].url == url


def test_synthesize_stream_yields_and_returns_report() -> None:
    from research_agent.synthesizer import synthesize_stream

    class StreamLLM:
        def decide_action(self, m, t):
            return {"action": "finish"}

        def generate(self, m):
            return "unused"

        def generate_stream(self, messages):
            yield "Phần 1 "
            yield "[https://a.com/x]"

    srcs = [Source(url="https://a.com/x", content="c", fetched_at=0.0)]
    gen = synthesize_stream("q", srcs, StreamLLM())
    chunks = list(gen)
    # The generator's return value (final Report) is on StopIteration.value;
    # iterating via list() discards it, so re-run capturing the return.
    assert "".join(chunks).startswith("Phần 1")


def test_synthesize_stream_return_value() -> None:
    from research_agent.synthesizer import synthesize_stream

    class StreamLLM:
        def generate_stream(self, messages):
            yield "Body [https://a.com/x]"

    srcs = [Source(url="https://a.com/x", content="c", fetched_at=0.0)]
    gen = synthesize_stream("q", srcs, StreamLLM())
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        report = stop.value
    assert report.body_markdown == "Body [1]"
    assert len(report.citations) == 1


def test_synthesize_stream_no_sources() -> None:
    from research_agent.synthesizer import synthesize_stream

    class StreamLLM:
        def generate_stream(self, messages):
            yield "should not be used"

    gen = synthesize_stream("q", [], StreamLLM(), language="vi")
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        report = stop.value
    assert report.no_information is True


# ---- ReportWriter (R7.1, R7.2, R7.5) ----
def test_write_report_to_path(tmp_path: Path) -> None:
    out = tmp_path / "sub" / "r.md"
    written = write_report("# hi", out)
    assert written == out and out.read_text(encoding="utf-8") == "# hi"


def test_write_report_failure_raises(tmp_path: Path) -> None:
    # A path whose parent is a file (not a dir) cannot be written.
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(ReportWriteError):
        write_report("data", blocker / "nested.md")


# ---- LLM retry (R11.2) ----
def test_retry_exhausts_then_raises() -> None:
    def always_fail():
        raise TransientLLMError("nope")

    with pytest.raises(LLMError):
        call_with_retry(always_fail, max_attempts=3, sleep=lambda _t: None, base_delay=0.0)


def test_retrying_provider_generate_stream_delegates() -> None:
    from research_agent.retry import RetryingLLMProvider

    class InnerStream:
        def decide_action(self, m, t):
            return {"action": "finish"}

        def generate(self, m):
            return "full"

        def generate_stream(self, messages):
            yield "a"
            yield "b"

    prov = RetryingLLMProvider(InnerStream(), max_attempts=3, sleep=lambda _t: None)
    assert "".join(prov.generate_stream([])) == "ab"


def test_retrying_provider_generate_stream_fallback() -> None:
    from research_agent.retry import RetryingLLMProvider

    class NoStream:
        def decide_action(self, m, t):
            return {"action": "finish"}

        def generate(self, m):
            return "single-shot"

    prov = RetryingLLMProvider(NoStream(), max_attempts=3, sleep=lambda _t: None)
    assert "".join(prov.generate_stream([])) == "single-shot"


# ---- Observability verbose toggle (R10.3) ----
def test_verbose_controls_reasoning() -> None:
    event = TraceEvent(
        type=TraceEventType.ACTION_SELECTED,
        round_index=1,
        sources_count=0,
        detail={"action": "search", "query": "q"},
        reasoning="because reasons",
    )
    assert "because reasons" in render_trace(event, verbose=True)
    assert "because reasons" not in render_trace(event, verbose=False)
