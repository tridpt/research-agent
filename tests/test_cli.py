"""Tests for the CLI wiring (argument parsing, validation, and main() flow).

The LLM/search/fetch I/O is replaced with fakes and the heavy run functions are
monkeypatched, so these tests exercise the CLI's own branching (input handling,
output-path selection, export dispatch, error handling, memory/recency wiring)
without any network access.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from research_agent import cli
from research_agent.errors import LLMError, ReportWriteError
from research_agent.models import Citation, Report, Source


def _report(body: str = "Body text [1].") -> Report:
    return Report(
        question="q",
        body_markdown=body,
        citations=(Citation(claim_ref="c0", url="https://a.com/x"),),
        sources=(Source(url="https://a.com/x", content="c", fetched_at=0.0),),
    )


@pytest.fixture
def api_env(monkeypatch):
    monkeypatch.setenv("RESEARCH_AGENT_API_KEY", "test-key")
    # Ensure optional providers are not configured for a deterministic wiring.
    for var in (
        "RESEARCH_AGENT_TAVILY_API_KEY",
        "RESEARCH_AGENT_SEARCH_ENDPOINT",
        "RESEARCH_AGENT_REPUTATION_FILE",
    ):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


@pytest.fixture
def stub_run_session(monkeypatch):
    """Replace run_session with a spy that returns a canned report."""
    calls: dict[str, object] = {}

    def fake_run_session(**kwargs):
        calls.update(kwargs)
        return _report()

    monkeypatch.setattr(cli, "run_session", fake_run_session)
    return calls


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------
def test_is_valid_question() -> None:
    assert cli.is_valid_question("hello")
    assert not cli.is_valid_question("")
    assert not cli.is_valid_question("   ")


def test_read_question_from_args() -> None:
    args = argparse.Namespace(question="  What is X?  ")
    assert cli.read_question(args, lambda: "unused") == "What is X?"


def test_read_question_prompts_until_valid() -> None:
    args = argparse.Namespace(question=None)
    answers = iter(["", "   ", "finally"])
    assert cli.read_question(args, lambda: next(answers)) == "finally"


def test_default_output_path_slugifies() -> None:
    path = cli._default_output_path("What is the CAP theorem?")
    assert path == Path("research-what-is-the-cap-theorem.md")


def test_default_output_path_falls_back_to_report() -> None:
    assert cli._default_output_path("!!!") == Path("research-report.md")


def test_summary_truncates_long_body() -> None:
    report = _report(body="x" * 1000)
    summary = cli._summary(report, max_chars=50)
    assert summary.endswith("...")
    assert len(summary) <= 60


def test_summary_keeps_short_body() -> None:
    assert cli._summary(_report(body="short")) == "short"


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------
def test_build_parser_defaults() -> None:
    args = cli.build_parser().parse_args(["my question"])
    assert args.question == "my question"
    assert args.reflect_iterations == 2
    assert args.verbose is False


def test_cli_overrides_skips_none() -> None:
    args = cli.build_parser().parse_args(["q", "--max-rounds", "5"])
    overrides = cli._cli_overrides(args)
    assert overrides["max_rounds"] == 5
    assert "max_sources" not in overrides


# --------------------------------------------------------------------------
# main(): error handling
# --------------------------------------------------------------------------
def test_main_missing_api_key_returns_2(monkeypatch) -> None:
    monkeypatch.delenv("RESEARCH_AGENT_API_KEY", raising=False)
    assert cli.main(["a question"]) == 2


def test_main_bad_reputation_file_returns_2(api_env, tmp_path) -> None:
    bad = tmp_path / "rep.json"
    bad.write_text("not json", encoding="utf-8")
    assert cli.main(["q", "--reputation-file", str(bad)]) == 2


def test_main_llm_error_returns_3(api_env, monkeypatch) -> None:
    def boom(**kwargs):
        raise LLMError("provider down")

    monkeypatch.setattr(cli, "run_session", boom)
    assert cli.main(["q", "-o", "out.md"]) == 3


def test_main_report_write_error_returns_4(api_env, stub_run_session, monkeypatch, tmp_path) -> None:
    def boom(markdown, path):
        raise ReportWriteError("no space")

    monkeypatch.setattr(cli, "write_report", boom)
    assert cli.main(["q", "-o", str(tmp_path / "out.md")]) == 4


# --------------------------------------------------------------------------
# main(): happy paths
# --------------------------------------------------------------------------
def test_main_writes_markdown_report(api_env, stub_run_session, tmp_path, capsys) -> None:
    out = tmp_path / "report.md"
    assert cli.main(["What is X?", "-o", str(out)]) == 0
    assert out.exists()
    printed = capsys.readouterr().out
    assert "Report written to:" in printed
    assert "Summary" in printed


def test_main_uses_default_output_path(api_env, stub_run_session, monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    assert cli.main(["Hello World"]) == 0
    assert (tmp_path / "research-hello-world.md").exists()


def test_main_reflect_mode_dispatch(api_env, monkeypatch, tmp_path) -> None:
    seen: dict[str, object] = {}

    def fake_reflect(**kwargs):
        seen.update(kwargs)
        return _report()

    monkeypatch.setattr(cli, "run_with_reflection", fake_reflect)
    assert cli.main(["q", "--reflect", "-o", str(tmp_path / "r.md")]) == 0
    assert seen["max_iterations"] == 2


def test_main_multi_agent_dispatch(api_env, monkeypatch, tmp_path) -> None:
    called = {"hit": False}

    def fake_multi(**kwargs):
        called["hit"] = True
        return _report()

    monkeypatch.setattr(cli, "run_multi_agent", fake_multi)
    assert cli.main(["q", "--multi-agent", "-o", str(tmp_path / "m.md")]) == 0
    assert called["hit"] is True


def test_main_memory_recall_and_store(api_env, stub_run_session, tmp_path) -> None:
    mem = tmp_path / "mem.json"
    out = tmp_path / "r.md"
    assert cli.main(["q", "--memory", "--memory-file", str(mem), "-o", str(out)]) == 0
    # The store file is created when the run's result is remembered.
    assert mem.exists()


def test_main_recency_directive_passed(api_env, stub_run_session, tmp_path) -> None:
    out = tmp_path / "r.md"
    assert cli.main(["latest news about AI in 2026", "-o", str(out)]) == 0
    assert stub_run_session["directive"] is not None


# --------------------------------------------------------------------------
# Export dispatch (PDF / DOCX) with fallback to Markdown
# --------------------------------------------------------------------------
def test_main_pdf_export_fallback_to_markdown(api_env, stub_run_session, monkeypatch, tmp_path) -> None:
    from research_agent import pdf_export

    def boom(question, markdown, path):
        raise pdf_export.PdfExportError("fpdf2 not installed")

    monkeypatch.setattr(pdf_export, "write_pdf", boom)
    out = tmp_path / "report.pdf"
    assert cli.main(["q", "-o", str(out)]) == 0
    assert (tmp_path / "report.md").exists()


def test_main_docx_export_fallback_to_markdown(api_env, stub_run_session, monkeypatch, tmp_path) -> None:
    from research_agent import docx_export

    def boom(question, markdown, path):
        raise docx_export.DocxExportError("python-docx not installed")

    monkeypatch.setattr(docx_export, "write_docx", boom)
    out = tmp_path / "report.docx"
    assert cli.main(["q", "-o", str(out)]) == 0
    assert (tmp_path / "report.md").exists()


def test_main_chat_loop_invoked(api_env, stub_run_session, monkeypatch, tmp_path) -> None:
    called = {"hit": False}

    def fake_chat(markdown, llm, input_fn, output_fn, language=None):
        called["hit"] = True

    monkeypatch.setattr(cli, "run_chat_loop", fake_chat)
    assert cli.main(["q", "--chat", "-o", str(tmp_path / "r.md")]) == 0
    assert called["hit"] is True


# --------------------------------------------------------------------------
# Helpers used by both CLI and the eval benchmark
# --------------------------------------------------------------------------
def test_build_search_and_fetch_wires_duckduckgo_default(api_env) -> None:
    from research_agent.config import resolve_settings
    from research_agent.search_tool import FallbackSearchTool

    settings = resolve_settings({"RESEARCH_AGENT_API_KEY": "k"}, {})
    search, fetch = cli._build_search_and_fetch(settings, use_cache=False)
    assert isinstance(search, FallbackSearchTool)
    assert fetch is not None


def test_build_search_and_fetch_includes_optional_providers(api_env, monkeypatch) -> None:
    monkeypatch.setenv("RESEARCH_AGENT_TAVILY_API_KEY", "tv-key")
    monkeypatch.setenv("RESEARCH_AGENT_SEARCH_ENDPOINT", "https://search.example/api")
    from research_agent.config import resolve_settings

    settings = resolve_settings({"RESEARCH_AGENT_API_KEY": "k"}, {})
    search, fetch = cli._build_search_and_fetch(settings, use_cache=True)
    # Tavily + custom + DuckDuckGo -> three providers behind the fallback.
    assert len(search._providers) == 3


def test_write_markdown_fallback_returns_none_on_error(monkeypatch, tmp_path) -> None:
    def boom(markdown, path):
        raise ReportWriteError("nope")

    monkeypatch.setattr(cli, "write_report", boom)
    assert cli._write_markdown_fallback("md", tmp_path / "x.pdf") is None
