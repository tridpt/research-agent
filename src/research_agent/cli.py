"""CLI: parse args, validate input, wire components, run a session."""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from pathlib import Path

from .agent import run_session
from .cache import CachingFetchTool, FetchCache
from .config import resolve_settings
from .errors import ConfigError, LLMError, ReportWriteError
from .fetch_tool import FetchTool, HttpFetchTool
from .llm import OpenAICompatibleProvider
from .memory import MemoryStore, format_memory_directive
from .models import Report
from .multi_agent import run_multi_agent
from .observability import make_emitter
from .reflection import run_with_reflection
from .render import render_markdown
from .report_writer import write_report
from .retry import RetryingLLMProvider
from .search_tool import (
    DuckDuckGoSearchTool,
    FallbackSearchTool,
    HttpSearchTool,
    SearchTool,
    TavilySearchTool,
)
from .synthesizer import synthesize
from .url_safety import public_http_url_error


def is_valid_question(raw: str) -> bool:
    """Pure: True iff the string has at least one non-whitespace character."""
    return bool(raw) and bool(raw.strip())


def read_question(args: argparse.Namespace, prompt_fn: Callable[[], str]) -> str:
    """Get the question from args, else prompt repeatedly until valid."""
    if args.question and is_valid_question(args.question):
        return args.question.strip()
    while True:
        candidate = prompt_fn()
        if is_valid_question(candidate):
            return candidate.strip()
        print("Please enter a non-empty research question.", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="research-agent",
        description="Autonomous AI research agent: searches, reads, and synthesizes a cited report.",
    )
    p.add_argument("question", nargs="?", help="The research question or topic.")
    p.add_argument("-o", "--out", dest="output_path", help="Path for the Markdown report.")
    p.add_argument("-v", "--verbose", action="store_true", help="Show reasoning for each step.")
    p.add_argument("--max-rounds", type=int, dest="max_rounds")
    p.add_argument("--max-sources", type=int, dest="max_sources")
    p.add_argument("--max-seconds", type=float, dest="max_seconds")
    p.add_argument("--min-domains", type=int, dest="min_domains", help="Encourage at least N distinct source domains.")
    p.add_argument("--max-per-domain", type=int, dest="max_per_domain", help="Never collect more than N sources per domain.")
    p.add_argument("--cache-dir", dest="cache_dir", help="Directory for the persistent fetch cache.")
    p.add_argument("--no-cache", action="store_true", help="Disable the persistent fetch cache.")
    p.add_argument(
        "--pdf",
        action="append",
        dest="pdf_paths",
        help="Explicitly approve one local PDF for this run (may be repeated).",
    )
    p.add_argument("--reflect", action="store_true", help="Enable self-critique: review the draft and research gaps.")
    p.add_argument("--reflect-iterations", type=int, dest="reflect_iterations", default=2, help="Max reflection revision rounds.")
    p.add_argument("--multi-agent", action="store_true", dest="multi_agent", help="Use a planner/researcher/writer agent team.")
    p.add_argument(
        "--memory",
        action="store_true",
        help="Recall relevant past research and remember this run's result.",
    )
    p.add_argument(
        "--memory-file",
        dest="memory_file",
        help="Path to the long-term memory store (default: .research_agent_memory.json).",
    )
    p.add_argument("--model", dest="model")
    p.add_argument("--provider", dest="provider")
    p.add_argument(
        "--style",
        dest="report_style",
        choices=["brief", "standard", "deep"],
        help="Report length/depth: brief, standard (default), or deep.",
    )
    return p


def _cli_overrides(args: argparse.Namespace) -> Mapping[str, object]:
    keys = [
        "output_path", "verbose", "max_rounds", "max_sources", "max_seconds",
        "model", "provider", "min_domains", "max_per_domain", "cache_dir",
        "pdf_paths", "report_style",
    ]
    return {k: getattr(args, k) for k in keys if getattr(args, k) is not None}


def _default_output_path(question: str) -> Path:
    slug = "".join(c if c.isalnum() else "-" for c in question.lower())[:40].strip("-") or "report"
    return Path(f"research-{slug}.md")


def _build_search_and_fetch(settings, use_cache: bool = True) -> tuple[SearchTool, FetchTool]:
    """Wire the search (with provider fallback) and fetch (optionally cached) tools.

    Shared by the CLI and the evaluation benchmark so both use identical I/O.
    Provider order: Tavily (if keyed) -> custom HTTP endpoint (if set) ->
    DuckDuckGo (free, always available as the final fallback).
    """
    providers: list[SearchTool] = []
    tavily_key = os.environ.get("RESEARCH_AGENT_TAVILY_API_KEY")
    if tavily_key:
        providers.append(TavilySearchTool(api_key=tavily_key, max_results=settings.budget.max_sources))
    search_endpoint = os.environ.get("RESEARCH_AGENT_SEARCH_ENDPOINT")
    if search_endpoint:
        providers.append(HttpSearchTool(endpoint=search_endpoint, api_key=settings.search_api_key))
    providers.append(DuckDuckGoSearchTool(max_results=settings.budget.max_sources))
    search: SearchTool = FallbackSearchTool(providers)

    fetch: FetchTool = HttpFetchTool(
        blocked_domains=settings.blocked_domains,
        per_source_char_limit=settings.per_source_char_limit,
    )
    if use_cache:
        cache_dir = settings.cache_dir or Path(".research_agent_cache")
        fetch = CachingFetchTool(
            fetch,
            FetchCache(cache_dir, ttl_seconds=settings.cache_ttl),
            url_validator=public_http_url_error,
        )
    return search, fetch


def _force_utf8_output() -> None:
    """Reconfigure stdout/stderr to UTF-8 so reports with Unicode (e.g. non-
    breaking hyphens, curly quotes) print correctly on Windows consoles that
    default to a legacy code page like cp1252."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: Sequence[str]) -> int:
    _force_utf8_output()
    args = build_parser().parse_args(list(argv))

    try:
        settings = resolve_settings(os.environ, _cli_overrides(args))
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    question = read_question(args, lambda: input("Research question: "))

    base_provider = OpenAICompatibleProvider(
        api_key=settings.api_key, base_url=settings.base_url, model=settings.model
    )
    llm = RetryingLLMProvider(base_provider, max_attempts=settings.max_llm_attempts)

    # Build search (provider fallback) and fetch (cached unless --no-cache).
    search, fetch = _build_search_and_fetch(settings, use_cache=not getattr(args, "no_cache", False))
    emit = make_emitter(settings.verbose)

    # Apply the configured report style to every synthesis path.
    synth_fn = partial(synthesize, style=settings.report_style)

    # Long-term memory (opt-in): recall relevant past research as trusted
    # background, and remember this run afterwards.
    memory_store: MemoryStore | None = None
    memory_directive: str | None = None
    if getattr(args, "memory", False):
        memory_path = Path(getattr(args, "memory_file", None) or ".research_agent_memory.json")
        memory_store = MemoryStore(memory_path)
        recalled = memory_store.recall(question)
        memory_directive = format_memory_directive(recalled) or None
        if memory_directive and settings.verbose:
            print(f"Recalled {len(recalled)} related past result(s) from memory.", file=sys.stderr)

    try:
        if getattr(args, "multi_agent", False):
            report: Report = run_multi_agent(
                question=question,
                settings=settings,
                llm=llm,
                search=search,
                fetch=fetch,
                synthesize_fn=synth_fn,
                clock=time.time,
                emit=emit,
            )
        elif getattr(args, "reflect", False):
            report = run_with_reflection(
                question=question,
                settings=settings,
                llm=llm,
                search=search,
                fetch=fetch,
                synthesize_fn=synth_fn,
                clock=time.time,
                emit=emit,
                max_iterations=getattr(args, "reflect_iterations", 2),
                directive=memory_directive,
            )
        else:
            report = run_session(
                question=question,
                settings=settings,
                llm=llm,
                search=search,
                fetch=fetch,
                synthesize_fn=synth_fn,
                clock=time.time,
                emit=emit,
                directive=memory_directive,
            )
    except LLMError as exc:
        print(f"LLM error: {exc}", file=sys.stderr)
        return 3

    if memory_store is not None:
        memory_store.add(report)

    markdown = render_markdown(report)
    out_path = settings.output_path or _default_output_path(question)

    # Direct PDF export when the output path ends in .pdf; otherwise Markdown.
    if out_path.suffix.lower() == ".pdf":
        from .pdf_export import PdfExportError, write_pdf

        try:
            written = write_pdf(question, markdown, out_path)
        except PdfExportError as exc:
            fallback = out_path.with_suffix(".md")
            print(f"PDF export unavailable ({exc}); writing Markdown instead.", file=sys.stderr)
            try:
                written = write_report(markdown, fallback)
            except ReportWriteError as write_exc:
                print(f"Failed to write report: {write_exc}", file=sys.stderr)
                return 4
        except OSError as exc:
            print(f"Failed to write PDF: {exc}", file=sys.stderr)
            return 4
    else:
        try:
            written = write_report(markdown, out_path)
        except ReportWriteError as exc:
            print(f"Failed to write report: {exc}", file=sys.stderr)
            return 4

    print(f"\nReport written to: {written}")
    print("\n--- Summary ---")
    print(_summary(report))
    return 0


def _summary(report: Report, max_chars: int = 600) -> str:
    body = report.body_markdown.strip()
    if len(body) <= max_chars:
        return body
    return body[:max_chars].rstrip() + " ..."


def run() -> None:
    """Console-script entry point."""
    raise SystemExit(main(sys.argv[1:]))


if __name__ == "__main__":
    run()
