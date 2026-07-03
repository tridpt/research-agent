"""Explainable, deterministic source-quality heuristics.

This is a ranking signal, not a fact-checker. It helps the agent prefer
official and evidence-rich sources while keeping the reasons visible to users.
"""
from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
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

# Curated, established/reputable sources (major news, reference works, and
# scholarly publishers). This is a transparent heuristic, not a fact-check: it
# nudges the agent toward sources with editorial standards above the open web,
# while still ranking official ``.gov``/``.edu``/``.int`` domains highest.
_ESTABLISHED_HOSTS = {
    # Wire services & established news
    "apnews.com",
    "reuters.com",
    "bbc.com",
    "bbc.co.uk",
    "npr.org",
    "theguardian.com",
    "nytimes.com",
    "wsj.com",
    "economist.com",
    "ft.com",
    "nationalgeographic.com",
    # Reference works
    "wikipedia.org",
    "britannica.com",
    # Scholarly publishers & repositories
    "nature.com",
    "science.org",
    "sciencedirect.com",
    "springer.com",
    "link.springer.com",
    "ieee.org",
    "acm.org",
    "arxiv.org",
    "jstor.org",
    "pubmed.ncbi.nlm.nih.gov",
    # Authoritative technical / standards bodies
    "mozilla.org",
    "developer.mozilla.org",
    "python.org",
    "w3.org",
    "ietf.org",
}


def _host_matches(host: str, domains: frozenset[str] | set[str]) -> bool:
    """Pure: True iff ``host`` equals or is a subdomain of any listed domain."""
    return any(host == domain or host.endswith("." + domain) for domain in domains)


# Per-domain score adjustments (points added/subtracted) loaded from a
# reputation file's optional ``weights`` map. Empty by default; a positive value
# nudges a domain up, a negative value down, on top of the category heuristics.
_DOMAIN_WEIGHTS: dict[str, int] = {}

# Snapshots of the built-in defaults so a loaded reputation file augments rather
# than replaces them, and so ``reset_reputation`` can restore them.
_DEFAULT_ESTABLISHED_HOSTS = frozenset(_ESTABLISHED_HOSTS)
_DEFAULT_LOW_EVIDENCE_HOSTS = frozenset(_LOW_EVIDENCE_HOSTS)


def _clean_hosts(values: object) -> set[str]:
    """Pure: normalize an iterable of domain strings into a lowercase set."""
    if not isinstance(values, (list, tuple, set, frozenset)):
        return set()
    return {str(v).strip().lower().lstrip(".") for v in values if str(v).strip()}


def _clean_weights(value: object) -> dict[str, int]:
    """Pure: normalize a {domain: points} map into lowercase host -> int.

    Non-numeric or unparseable values are skipped; each weight is clamped to
    [-100, 100] so a single domain can never dominate the 0-100 score scale.
    """
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, int] = {}
    for raw_host, raw_points in value.items():
        host = str(raw_host).strip().lower().lstrip(".")
        if not host:
            continue
        try:
            points = int(raw_points)
        except (TypeError, ValueError):
            continue
        cleaned[host] = max(-100, min(100, points))
    return cleaned


def apply_reputation(
    established: set[str] | None = None,
    low_evidence: set[str] | None = None,
    weights: dict[str, int] | None = None,
) -> None:
    """Augment the built-in reputation lists with extra domains (configuration).

    Passing a set adds those domains on top of the built-in defaults; the change
    affects subsequent ``assess_source`` calls. ``weights`` sets per-domain score
    adjustments (points added on top of the category heuristic) and replaces any
    previously applied weights.
    """
    global _ESTABLISHED_HOSTS, _LOW_EVIDENCE_HOSTS, _DOMAIN_WEIGHTS
    _ESTABLISHED_HOSTS = set(_DEFAULT_ESTABLISHED_HOSTS) | (established or set())
    _LOW_EVIDENCE_HOSTS = set(_DEFAULT_LOW_EVIDENCE_HOSTS) | (low_evidence or set())
    _DOMAIN_WEIGHTS = dict(weights or {})


def reset_reputation() -> None:
    """Restore the built-in reputation lists (used by tests)."""
    global _ESTABLISHED_HOSTS, _LOW_EVIDENCE_HOSTS, _DOMAIN_WEIGHTS
    _ESTABLISHED_HOSTS = set(_DEFAULT_ESTABLISHED_HOSTS)
    _LOW_EVIDENCE_HOSTS = set(_DEFAULT_LOW_EVIDENCE_HOSTS)
    _DOMAIN_WEIGHTS = {}


def _weight_for(host: str) -> tuple[int, str | None]:
    """Pure: the configured score adjustment for ``host`` (0 if none).

    Matches an exact host or any parent domain (so a weight on ``example.com``
    also applies to ``blog.example.com``). Returns ``(points, matched_domain)``.
    """
    for domain, points in _DOMAIN_WEIGHTS.items():
        if host == domain or host.endswith("." + domain):
            return points, domain
    return 0, None


def load_reputation_file(path: str | Path) -> tuple[set[str], set[str], dict[str, int]]:
    """Read a JSON reputation file -> (established, low_evidence, weights).

    Expected shape: {"established": ["reuters.com", ...],
                     "low_evidence": ["example-forum.com", ...],
                     "weights": {"my-lab.example": 15, "spam.example": -30}}.
    Raises ValueError if the file is missing or malformed.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"could not read reputation file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("reputation file must be a JSON object")
    return (
        _clean_hosts(data.get("established")),
        _clean_hosts(data.get("low_evidence")),
        _clean_weights(data.get("weights")),
    )


def configure_reputation_from_file(path: str | Path) -> None:
    """Load a reputation file and apply it (raises ValueError on failure)."""
    established, low_evidence, weights = load_reputation_file(path)
    apply_reputation(established, low_evidence, weights)


def configure_reputation_from_mapping(data: object) -> None:
    """Apply reputation from an already-parsed mapping (e.g. from the UI).

    ``data`` should be a dict with optional ``established``/``low_evidence``
    lists and a ``weights`` map. Raises ValueError if it is not a JSON object.
    """
    if not isinstance(data, dict):
        raise ValueError("reputation data must be a JSON object")
    apply_reputation(
        _clean_hosts(data.get("established")),
        _clean_hosts(data.get("low_evidence")),
        _clean_weights(data.get("weights")),
    )


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
    elif _host_matches(host, _DIRECT_DATA_HOSTS):
        score += 20
        reasons.append("direct data provider")
    elif _host_matches(host, _ESTABLISHED_HOSTS):
        score += 18
        reasons.append("established or reputable source")
    elif _host_matches(host, _LOW_EVIDENCE_HOSTS):
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

    # Apply any user-configured per-domain weight on top of the heuristics.
    weight, matched = _weight_for(host)
    if weight:
        score += weight
        sign = "+" if weight > 0 else ""
        reasons.append(f"custom reputation weight ({sign}{weight} for {matched})")

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
