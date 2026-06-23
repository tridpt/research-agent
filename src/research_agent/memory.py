"""Long-term memory across research sessions.

A small, file-based store of finished research (question + a short summary +
the source URLs). Before a new run, the most relevant past entries can be
recalled and injected as *trusted* reference context, so the agent can build on
earlier work instead of starting from scratch each time.

The relevance scoring, summarization, and directive formatting are pure
functions (easy to test); only ``MemoryStore`` touches the disk, mirroring the
``FetchCache`` design.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from .models import Report

# Words too common to carry topical signal when matching past research.
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
        "what", "how", "why", "when", "who", "which", "does", "do", "with", "vs",
        "between", "about", "from", "by", "at", "as", "be", "it", "its", "into",
    }
)
_WORD_RE = re.compile(r"[a-z0-9]+")

DEFAULT_MAX_RECORDS = 200


@dataclass(frozen=True)
class MemoryRecord:
    """One remembered research result."""

    question: str
    summary: str
    sources: tuple[str, ...] = ()
    created_at: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "question": self.question,
            "summary": self.summary,
            "sources": list(self.sources),
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(data: dict[str, object]) -> MemoryRecord:
        raw_sources = data.get("sources")
        sources = raw_sources if isinstance(raw_sources, list) else []
        created = data.get("created_at", 0.0)
        return MemoryRecord(
            question=str(data.get("question", "")),
            summary=str(data.get("summary", "")),
            sources=tuple(str(s) for s in sources),
            created_at=float(created) if isinstance(created, (int, float, str)) else 0.0,
        )


def tokenize(text: str) -> frozenset[str]:
    """Pure: lowercase content words of ``text`` (stopwords removed)."""
    return frozenset(
        w for w in _WORD_RE.findall((text or "").lower()) if w not in _STOPWORDS and len(w) > 1
    )


def relevance_score(question: str, record: MemoryRecord) -> float:
    """Pure: Jaccard similarity between a question and a remembered question.

    Returns a value in [0, 1]; 0 when either side has no content words.
    """
    a = tokenize(question)
    b = tokenize(record.question)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def select_relevant(
    records: list[MemoryRecord],
    question: str,
    k: int = 3,
    min_score: float = 0.15,
) -> tuple[MemoryRecord, ...]:
    """Pure: top-``k`` past records most relevant to ``question``.

    Skips an exact-duplicate question and anything below ``min_score`` so an
    unrelated history never pollutes the prompt. Ties keep the more recent entry.
    """
    q_norm = question.strip().lower()
    scored = [
        (relevance_score(question, r), r.created_at, r)
        for r in records
        if r.question.strip().lower() != q_norm
    ]
    relevant = [item for item in scored if item[0] >= min_score]
    relevant.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return tuple(r for _, _, r in relevant[: max(0, k)])


def summarize_for_memory(report: Report, max_chars: int = 600) -> str:
    """Pure: a compact plain-text summary of a report body for storage."""
    body = (report.body_markdown or "").strip()
    # Collapse markdown headings/whitespace into a flat snippet.
    flat = re.sub(r"[#>*_`]", "", body)
    flat = re.sub(r"\s+", " ", flat).strip()
    if len(flat) <= max_chars:
        return flat
    return flat[:max_chars].rstrip() + "…"


def format_memory_directive(records: tuple[MemoryRecord, ...]) -> str:
    """Pure: turn recalled records into a trusted instruction for the agent.

    Returns an empty string when there is nothing relevant to recall.
    """
    if not records:
        return ""
    lines = [
        "You have prior related research from earlier sessions. Use it only as "
        "background context to focus this run; it may be outdated, so verify "
        "anything time-sensitive with a fresh search and cite newly read sources:",
    ]
    for i, r in enumerate(records, start=1):
        lines.append(f"{i}. Earlier question: {r.question}")
        if r.summary:
            lines.append(f"   Summary: {r.summary}")
    return "\n".join(lines)


def build_record(report: Report, *, now: float, max_chars: int = 600) -> MemoryRecord:
    """Pure: construct a MemoryRecord from a finished report."""
    return MemoryRecord(
        question=report.question,
        summary=summarize_for_memory(report, max_chars),
        sources=tuple(s.url for s in report.sources),
        created_at=now,
    )


class MemoryStore:
    """File-based JSON store of past research records (newest first)."""

    def __init__(self, path: Path, max_records: int = DEFAULT_MAX_RECORDS) -> None:
        self.path = Path(path)
        self.max_records = max_records

    def load(self) -> list[MemoryRecord]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(data, list):
            return []
        return [MemoryRecord.from_dict(d) for d in data if isinstance(d, dict)]

    def recall(self, question: str, k: int = 3, min_score: float = 0.15) -> tuple[MemoryRecord, ...]:
        """Most relevant past records for ``question`` (best-effort)."""
        return select_relevant(self.load(), question, k=k, min_score=min_score)

    def add(self, report: Report, *, now: float | None = None) -> None:
        """Persist a finished report as a new memory record (best-effort)."""
        if report.no_information and not report.sources:
            return
        record = build_record(report, now=now if now is not None else time.time())
        records = [record, *self.load()]
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = [r.to_dict() for r in records[: self.max_records]]
            self.path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            # Memory is an enhancement; a write failure must not break research.
            pass
