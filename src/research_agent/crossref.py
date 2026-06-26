"""Scholarly-work lookup via the CrossRef REST API (no key).

Searches CrossRef for academic works (title, authors, year, DOI) — complements
arXiv with peer-reviewed/journal coverage. Parsing/formatting are pure; only
``fetch_crossref`` performs network I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CROSSREF_API = "https://api.crossref.org/works"
USER_AGENT = "research-agent/0.1 (mailto:research-agent@example.com)"


class CrossRefError(ValueError):
    """Raised when a query is invalid or no works could be parsed."""


@dataclass(frozen=True)
class Work:
    title: str
    authors: tuple[str, ...]
    year: str
    doi: str
    container: str


def normalize_query(raw: str) -> str:
    """Pure: collapse whitespace; reject empty."""
    cleaned = " ".join((raw or "").split())
    if not cleaned:
        raise CrossRefError("empty query")
    return cleaned


def _authors(item: dict) -> tuple[str, ...]:
    names: list[str] = []
    for a in item.get("author", []) or []:
        if not isinstance(a, dict):
            continue
        name = " ".join(p for p in (a.get("given"), a.get("family")) if p).strip()
        if name:
            names.append(name)
    return tuple(names)


def _year(item: dict) -> str:
    for key in ("published-print", "published-online", "issued", "created"):
        block = item.get(key)
        if isinstance(block, dict):
            parts = block.get("date-parts")
            if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
                return str(parts[0][0])
    return ""


def parse_crossref(payload: Any, limit: int = 3) -> tuple[Work, ...]:
    """Pure: parse a CrossRef works response into a list of Work."""
    if not isinstance(payload, dict):
        raise CrossRefError("malformed response")
    message = payload.get("message")
    items = message.get("items") if isinstance(message, dict) else None
    if not isinstance(items, list) or not items:
        raise CrossRefError("no works found")
    works: list[Work] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title_list = item.get("title") or []
        title = str(title_list[0]).strip() if isinstance(title_list, list) and title_list else ""
        if not title:
            continue
        container_list = item.get("container-title") or []
        container = str(container_list[0]).strip() if isinstance(container_list, list) and container_list else ""
        works.append(Work(
            title=title, authors=_authors(item), year=_year(item),
            doi=str(item.get("DOI") or "").strip(), container=container,
        ))
        if len(works) >= max(1, limit):
            break
    if not works:
        raise CrossRefError("no works found")
    return tuple(works)


def format_works(works: tuple[Work, ...]) -> str:
    """Pure: a readable plain-text block of works."""
    lines = ["CrossRef results:"]
    for i, w in enumerate(works, start=1):
        authors = ", ".join(w.authors[:4]) + (" et al." if len(w.authors) > 4 else "")
        meta = " · ".join(p for p in (authors, w.year, w.container) if p)
        doi = f"https://doi.org/{w.doi}" if w.doi else ""
        lines.append(f"{i}. {w.title}\n   {meta}\n   {doi}")
    return "\n".join(lines)


def fetch_crossref(query: str, *, limit: int = 3, timeout: float = 15.0) -> tuple[str, str]:
    """Fetch scholarly works; return (source_url, formatted content)."""
    import httpx

    clean = normalize_query(query)
    params: dict[str, str | int] = {"query": clean, "rows": max(1, limit)}
    try:
        resp = httpx.get(
            CROSSREF_API, params=params, timeout=timeout,
            headers={"User-Agent": USER_AGENT}, follow_redirects=True,
        )
        resp.raise_for_status()
        payload = resp.json()
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        raise CrossRefError(f"could not fetch works: {exc}") from exc
    except ValueError as exc:  # pragma: no cover - invalid JSON
        raise CrossRefError(f"invalid works response: {exc}") from exc
    works = parse_crossref(payload, limit=limit)
    page_url = f"https://doi.org/{works[0].doi}" if works[0].doi else f"https://search.crossref.org/?q={clean.replace(' ', '+')}"
    return page_url, format_works(works)
