"""Lightweight evaluation harness for comparing agent modes.

Computes objective, deterministic metrics about a finished Report so different
modes (normal / reflect / multi-agent) or models can be compared on the same
question set. These metrics do not judge prose quality (that needs an LLM or
human); they measure grounding signals that correlate with a useful report.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .content import host_of
from .models import Report
from .source_quality import source_quality_summary


@dataclass(frozen=True)
class ReportMetrics:
    question: str
    n_sources: int
    n_domains: int
    n_citations: int
    body_chars: int
    has_information: bool
    grounded: bool  # True if it has sources AND at least one citation
    avg_source_quality: float = 0.0  # mean 0-100 quality score of its sources

    def as_row(self) -> dict[str, object]:
        return {
            "question": self.question,
            "sources": self.n_sources,
            "domains": self.n_domains,
            "citations": self.n_citations,
            "chars": self.body_chars,
            "avg_quality": round(self.avg_source_quality, 1),
            "has_info": self.has_information,
            "grounded": self.grounded,
        }


def evaluate_report(report: Report) -> ReportMetrics:
    """Compute deterministic metrics for a single report."""
    domains = {host_of(s.url) for s in report.sources}
    n_sources = len(report.sources)
    n_citations = len(report.citations)
    if report.sources:
        avg_quality = sum(
            source_quality_summary(s).score for s in report.sources
        ) / n_sources
    else:
        avg_quality = 0.0
    return ReportMetrics(
        question=report.question,
        n_sources=n_sources,
        n_domains=len(domains),
        n_citations=n_citations,
        body_chars=len(report.body_markdown),
        has_information=not report.no_information,
        grounded=n_sources > 0 and n_citations > 0,
        avg_source_quality=avg_quality,
    )


def aggregate(metrics: list[ReportMetrics]) -> dict[str, float]:
    """Average the numeric metrics across many reports (for a mode/run)."""
    if not metrics:
        return {
            "avg_sources": 0.0,
            "avg_domains": 0.0,
            "avg_citations": 0.0,
            "avg_chars": 0.0,
            "avg_quality": 0.0,
            "grounded_rate": 0.0,
            "info_rate": 0.0,
        }
    n = len(metrics)
    return {
        "avg_sources": sum(m.n_sources for m in metrics) / n,
        "avg_domains": sum(m.n_domains for m in metrics) / n,
        "avg_citations": sum(m.n_citations for m in metrics) / n,
        "avg_chars": sum(m.body_chars for m in metrics) / n,
        "avg_quality": sum(m.avg_source_quality for m in metrics) / n,
        "grounded_rate": sum(1 for m in metrics if m.grounded) / n,
        "info_rate": sum(1 for m in metrics if m.has_information) / n,
    }


# A mode runner takes a question and returns a finished Report.
ModeRunner = Callable[[str], Report]


def evaluate_modes(
    questions: Sequence[str],
    runners: dict[str, ModeRunner],
) -> dict[str, list[ReportMetrics]]:
    """Run every mode over every question and collect per-report metrics.

    ``runners`` maps a mode label (e.g. "normal", "reflect") to a callable that
    produces a Report for a question. I/O lives in the injected runners, so this
    orchestrator is easy to test with fakes.
    """
    results: dict[str, list[ReportMetrics]] = {}
    for mode, runner in runners.items():
        metrics: list[ReportMetrics] = []
        for question in questions:
            metrics.append(evaluate_report(runner(question)))
        results[mode] = metrics
    return results


def compare_modes(results: dict[str, list[ReportMetrics]]) -> dict[str, dict[str, float]]:
    """Pure: aggregate each mode's metrics into a comparable summary."""
    return {mode: aggregate(metrics) for mode, metrics in results.items()}


_METRIC_COLUMNS = (
    ("avg_sources", "Avg sources"),
    ("avg_domains", "Avg domains"),
    ("avg_citations", "Avg citations"),
    ("avg_chars", "Avg chars"),
    ("avg_quality", "Avg quality"),
    ("grounded_rate", "Grounded rate"),
    ("info_rate", "Info rate"),
)


def format_comparison_markdown(summary: dict[str, dict[str, float]]) -> str:
    """Pure: render a mode-comparison summary as a Markdown table."""
    if not summary:
        return "_No evaluation results._"
    header = "| Mode | " + " | ".join(label for _, label in _METRIC_COLUMNS) + " |"
    divider = "|" + "---|" * (len(_METRIC_COLUMNS) + 1)
    rows = [header, divider]
    for mode, agg in summary.items():
        cells = [f"{agg.get(key, 0.0):.2f}" for key, _ in _METRIC_COLUMNS]
        rows.append(f"| {mode} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


# A small default question set for benchmarking.
DEFAULT_QUESTIONS = [
    "What is the CAP theorem in distributed systems?",
    "What are the main differences between SQL and NoSQL databases?",
    "How does HTTPS encryption work?",
    "What is retrieval-augmented generation?",
]


def _build_runners(settings, llm, search, fetch, modes: Sequence[str]) -> dict[str, ModeRunner]:
    """Wire real mode runners (normal/reflect/multi-agent) for a benchmark."""
    import time

    from .agent import run_session
    from .multi_agent import run_multi_agent
    from .observability import make_emitter
    from .reflection import run_with_reflection
    from .synthesizer import synthesize

    emit = make_emitter(False)
    available: dict[str, ModeRunner] = {
        "normal": lambda q: run_session(q, settings, llm, search, fetch, synthesize, time.time, emit),
        "reflect": lambda q: run_with_reflection(q, settings, llm, search, fetch, synthesize, time.time, emit),
        "multi-agent": lambda q: run_multi_agent(q, settings, llm, search, fetch, synthesize, time.time, emit),
    }
    return {m: available[m] for m in modes if m in available}


def main(argv: Sequence[str] | None = None) -> int:
    """Benchmark the agent's modes on a question set and print a comparison.

    Reuses the same provider/search/fetch wiring as the CLI.
    """
    import argparse
    import os
    import time  # noqa: F401  (used indirectly by runners)

    from .cli import _build_search_and_fetch
    from .config import resolve_settings
    from .errors import ConfigError
    from .llm import OpenAICompatibleProvider
    from .retry import RetryingLLMProvider

    parser = argparse.ArgumentParser(prog="research-agent-eval", description="Compare agent modes.")
    parser.add_argument("--modes", default="normal,reflect,multi-agent",
                        help="Comma-separated modes to compare.")
    parser.add_argument("--questions", action="append",
                        help="A question to benchmark (repeatable); defaults to a built-in set.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        settings = resolve_settings(os.environ, {})
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 2

    llm = RetryingLLMProvider(
        OpenAICompatibleProvider(api_key=settings.api_key, base_url=settings.base_url, model=settings.model),
        max_attempts=settings.max_llm_attempts,
    )
    search, fetch = _build_search_and_fetch(settings)
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    questions = args.questions or DEFAULT_QUESTIONS

    results = evaluate_modes(questions, _build_runners(settings, llm, search, fetch, modes))
    print(format_comparison_markdown(compare_modes(results)))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
