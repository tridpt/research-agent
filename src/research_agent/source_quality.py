"""Explainable, deterministic source-quality heuristics.

This is a ranking signal, not a fact-checker. It helps the agent prefer
official and evidence-rich sources while keeping the reasons visible to users.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from .models import SearchResult, Source

_LOW_EVIDENCE_HOSTS = {
    "facebook.com",
    "instagram.com",
    "pinterest.com",
    "quora.com",
    "reddit.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "youtube.com",
}
_DIRECT_DATA_HOSTS = {"wttr.in"}


@dataclass(frozen=True)
class SourceQuality:
    """An explainable quality estimate for one URL and its extracted content."""

    score: int
    label: str
    reason: str


def assess_source(url: str, content: str | None = None) -> SourceQuality:
    """Score a source using domain type and available extracted evidence."""
    parsed = urlsplit(url)
    if parsed.scheme == "local-pdf":
        score = 90
        reason = "user-provided PDF document"
        if content is not None and len(re.sub(r"\s+", "", content)) >= 600:
            score = 100
            reason += "; substantial extracted evidence"
        return SourceQuality(score=score, label="high", reason=reason)

    host = (parsed.hostname or "").lower().rstrip(".")
    labels = host.split(".") if host else []
    score = 50
    reasons: list[str] = []

    is_official = "gov" in labels or "edu" in labels or host.endswith(".int")
    if is_official:
        score += 35
        reasons.append("official or academic domain")
    elif host in _DIRECT_DATA_HOSTS:
        score += 20
        reasons.append("direct data provider")
    elif any(host == domain or host.endswith("." + domain) for domain in _LOW_EVIDENCE_HOSTS):
        score -= 25
        reasons.append("social or user-generated platform")
    else:
        reasons.append("general web source")

    if content is not None:
        evidence_chars = len(re.sub(r"\s+", "", content))
        if evidence_chars < 80:
            if host in _DIRECT_DATA_HOSTS:
                reasons.append("concise direct reading")
            else:
                score -= 25
                reasons.append("very little extractable evidence")
        elif evidence_chars < 250:
            score -= 10
            reasons.append("limited extractable evidence")
        elif evidence_chars >= 600:
            score += 10
            reasons.append("substantial extracted evidence")

    score = max(0, min(100, score))
    label = "high" if score >= 75 else "medium" if score >= 50 else "low"
    return SourceQuality(score=score, label=label, reason="; ".join(reasons))


def rank_search_results(results: Sequence[SearchResult]) -> tuple[SearchResult, ...]:
    """Return results ordered by quality while preserving ties' original order."""
    return tuple(
        result
        for _, result in sorted(
            enumerate(results),
            key=lambda item: (-assess_source(item[1].url).score, item[0]),
        )
    )


def source_quality_summary(source: Source) -> SourceQuality:
    """Convenience wrapper for a fetched source with actual evidence text."""
    return assess_source(source.url, source.content)


def is_local_pdf_source(url: str) -> bool:
    """True when a source identifies an explicitly user-provided PDF."""
    return urlsplit(url).scheme == "local-pdf"


def source_display_name(url: str) -> str:
    """Return a safe human label without exposing a local temporary path."""
    parsed = urlsplit(url)
    if parsed.scheme == "local-pdf":
        name = unquote(parsed.netloc or parsed.path.lstrip("/")) or "document.pdf"
        return f"User-provided PDF: {name}"
    return url
