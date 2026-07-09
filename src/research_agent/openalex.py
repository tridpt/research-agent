"""OpenAlex scholarly-works lookup tool.

Searches OpenAlex (https://openalex.org) — a large, open index of scholarly
works across every discipline — via its public REST API (no API key). Returns
the top matching works' title, authors, host venue, year, and a resolvable link
(DOI when available). This complements ``crossref`` (DOI registry), ``arxiv``
(preprints), and ``pubmed`` (biomedical) with the broadest general-purpose
academic coverage.

The single HTTP call lives behind ``fetch_openalex`` while all parsing and
formatting stay pure so they can be unit-tested without any network.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

WORKS_API = "https://api.openalex.org/works"
# OpenAlex asks callers to identify themselves for the faster "polite pool".
USER_AGENT = "research-agent/0.1 (+https://github.com/tridpt/research-agent)"


class OpenAlexError(ValueError):
    """Raised when a query is invalid or no works could be parsed."""


@dataclass(frozen=True)
class OpenAlexWork:
    title: str
    authors: tuple[str, ...]
    venue: str
    year: str
    url: str


def normalize_query(raw: str) -> str:
    """Pure: collapse whitespace in a free-text query; reject empty input."""
    cleaned = " ".join((raw or "").split())
    if not cleaned:
        raise OpenAlexError("empty query")
    return cleaned


def works_params(query: str, per_page: int = 3) -> dict[str, Any]:
    """Pure: the OpenAlex ``/works`` query parameters for a topic search."""
    return {
        "search": query,
        "per_page": max(1, per_page),
        # Only request the fields we render, keeping the response small.
        "select": "id,doi,title,publication_year,authorships,primary_location",
    }


def _parse_authors(authorships: Any) -> tuple[str, ...]:
    """Pure: pull author display names from an ``authorships`` list."""
    if not isinstance(authorships, list):
        return ()
    names: list[str] = []
    for entry in authorships:
        if not isinstance(entry, dict):
            continue
        author = entry.get("author")
        if isinstance(author, dict):
            name = str(author.get("display_name") or "").strip()
            if name:
                names.append(name)
    return tuple(names)


def _resolve_url(work: dict[str, Any]) -> str:
    """Pure: prefer a DOI link, then the landing page, then the OpenAlex id."""
    doi = str(work.get("doi") or "").strip()
    if doi:
        return doi if doi.startswith("http") else f"https://doi.org/{doi}"
    location = work.get("primary_location")
    if isinstance(location, dict):
        landing = str(location.get("landing_page_url") or "").strip()
        if landing:
            return landing
    return str(work.get("id") or "").strip()


def _venue_name(work: dict[str, Any]) -> str:
    """Pure: the host venue (journal/conference) display name, if any."""
    location = work.get("primary_location")
    if isinstance(location, dict):
        source = location.get("source")
        if isinstance(source, dict):
            return str(source.get("display_name") or "").strip()
    return ""


def parse_works(payload: Any) -> tuple[OpenAlexWork, ...]:
    """Pure: parse an OpenAlex ``/works`` response into works (order preserved).

    Raises OpenAlexError when the response is malformed or contains no usable
    works.
    """
    if not isinstance(payload, dict):
        raise OpenAlexError("malformed response")
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        raise OpenAlexError("no works found")

    works: list[OpenAlexWork] = []
    for work in results:
        if not isinstance(work, dict):
            continue
        title = str(work.get("title") or "").strip()
        if not title:
            continue
        year = work.get("publication_year")
        works.append(
            OpenAlexWork(
                title=title,
                authors=_parse_authors(work.get("authorships")),
                venue=_venue_name(work),
                year=str(year) if year else "",
                url=_resolve_url(work),
            )
        )
    if not works:
        raise OpenAlexError("no usable works")
    return tuple(works)


def format_works(works: tuple[OpenAlexWork, ...]) -> str:
    """Pure: a readable, citation-style plain-text block for agent context."""
    blocks: list[str] = ["OpenAlex results:"]
    for i, w in enumerate(works, start=1):
        authors = ", ".join(w.authors[:4]) + (" et al." if len(w.authors) > 4 else "")
        meta = " · ".join(part for part in (authors, w.venue, w.year) if part)
        line = f"{i}. {w.title}"
        if meta:
            line += f"\n   {meta}"
        if w.url:
            line += f"\n   {w.url}"
        blocks.append(line)
    return "\n\n".join(blocks)


def fetch_openalex(query: str, *, per_page: int = 3, timeout: float = 20.0) -> tuple[str, str]:
    """Fetch OpenAlex results; return (source_url, formatted content).

    Network I/O is isolated here so parsing/formatting stay pure. Raises
    OpenAlexError on any network or parsing failure (including rate limiting).
    """
    import httpx

    clean = normalize_query(query)
    try:
        resp = httpx.get(
            WORKS_API,
            params=works_params(clean, per_page),
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        resp.raise_for_status()
        works = parse_works(resp.json())
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        raise OpenAlexError(f"could not fetch OpenAlex results: {exc}") from exc
    except ValueError as exc:
        if isinstance(exc, OpenAlexError):
            raise
        raise OpenAlexError(f"invalid OpenAlex response: {exc}") from exc

    page_url = works[0].url or f"https://openalex.org/works?search={clean.replace(' ', '+')}"
    return page_url, format_works(works)
