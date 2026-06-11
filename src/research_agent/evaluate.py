"""Lightweight evaluation harness for comparing agent modes.

Computes objective, deterministic metrics about a finished Report so different
modes (normal / reflect / multi-agent) or models can be compared on the same
question set. These metrics do not judge prose quality (that needs an LLM or
human); they measure grounding signals that correlate with a useful report.
"""
from __future__ import annotations

from dataclasses import dataclass

from .content import host_of
from .models import Report


@dataclass(frozen=True)
class ReportMetrics:
    question: str
    n_sources: int
    n_domains: int
    n_citations: int
    body_chars: int
    has_information: bool
    grounded: bool  # True if it has sources AND at least one citation

    def as_row(self) -> dict[str, object]:
        return {
            "question": self.question,
            "sources": self.n_sources,
            "domains": self.n_domains,
            "citations": self.n_citations,
            "chars": self.body_chars,
            "has_info": self.has_information,
            "grounded": self.grounded,
        }


def evaluate_report(report: Report) -> ReportMetrics:
    """Compute deterministic metrics for a single report."""
    domains = {host_of(s.url) for s in report.sources}
    n_sources = len(report.sources)
    n_citations = len(report.citations)
    return ReportMetrics(
        question=report.question,
        n_sources=n_sources,
        n_domains=len(domains),
        n_citations=n_citations,
        body_chars=len(report.body_markdown),
        has_information=not report.no_information,
        grounded=n_sources > 0 and n_citations > 0,
    )


def aggregate(metrics: list[ReportMetrics]) -> dict[str, float]:
    """Average the numeric metrics across many reports (for a mode/run)."""
    if not metrics:
        return {"avg_sources": 0.0, "avg_domains": 0.0, "avg_citations": 0.0, "grounded_rate": 0.0}
    n = len(metrics)
    return {
        "avg_sources": sum(m.n_sources for m in metrics) / n,
        "avg_domains": sum(m.n_domains for m in metrics) / n,
        "avg_citations": sum(m.n_citations for m in metrics) / n,
        "grounded_rate": sum(1 for m in metrics if m.grounded) / n,
    }


# A small default question set for benchmarking.
DEFAULT_QUESTIONS = [
    "What is the CAP theorem in distributed systems?",
    "What are the main differences between SQL and NoSQL databases?",
    "How does HTTPS encryption work?",
    "What is retrieval-augmented generation?",
]
