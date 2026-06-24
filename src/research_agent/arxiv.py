"""arXiv academic-paper lookup tool.

Searches arXiv's public Atom API (no key) and returns the top matching papers'
titles, authors, and abstracts. XML parsing/formatting are pure functions so
they can be unit-tested without any network; the HTTP call lives behind
``fetch_arxiv``.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

ARXIV_API = "http://export.arxiv.org/api/query"
_ATOM = "{http://www.w3.org/2005/Atom}"
USER_AGENT = "research-agent/0.1 (+https://github.com/tridpt/research-agent)"


class ArxivError(ValueError):
    """Raised when a query is invalid or no papers could be parsed."""


@dataclass(frozen=True)
class ArxivPaper:
    title: str
    authors: tuple[str, ...]
    summary: str
    url: str
    published: str


def normalize_query(raw: str) -> str:
    """Pure: trim a free-text query; reject empty input."""
    cleaned = " ".join((raw or "").split())
    if not cleaned:
        raise ArxivError("empty query")
    return cleaned


def parse_arxiv_atom(xml_text: str) -> tuple[ArxivPaper, ...]:
    """Pure: parse an arXiv Atom feed into papers (raises if none/invalid)."""
    if not xml_text or not xml_text.strip():
        raise ArxivError("empty response")
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ArxivError(f"invalid XML: {exc}") from exc

    papers: list[ArxivPaper] = []
    for entry in root.findall(f"{_ATOM}entry"):
        title = (entry.findtext(f"{_ATOM}title") or "").strip().replace("\n", " ")
        summary = (entry.findtext(f"{_ATOM}summary") or "").strip().replace("\n", " ")
        url = (entry.findtext(f"{_ATOM}id") or "").strip()
        published = (entry.findtext(f"{_ATOM}published") or "").strip()[:10]
        authors = tuple(
            name.strip()
            for author in entry.findall(f"{_ATOM}author")
            if (name := author.findtext(f"{_ATOM}name"))
        )
        if title and summary:
            papers.append(
                ArxivPaper(title=title, authors=authors, summary=summary, url=url, published=published)
            )
    if not papers:
        raise ArxivError("no papers found")
    return tuple(papers)


def format_papers(papers: tuple[ArxivPaper, ...], max_summary_chars: int = 700) -> str:
    """Pure: a readable plain-text block summarizing the papers."""
    blocks: list[str] = ["arXiv results:"]
    for i, p in enumerate(papers, start=1):
        authors = ", ".join(p.authors[:4]) + (" et al." if len(p.authors) > 4 else "")
        summary = p.summary
        if max_summary_chars > 0 and len(summary) > max_summary_chars:
            summary = summary[:max_summary_chars].rstrip() + "…"
        meta = " · ".join(part for part in (authors, p.published, p.url) if part)
        blocks.append(f"{i}. {p.title}\n   {meta}\n   {summary}")
    return "\n\n".join(blocks)


def fetch_arxiv(query: str, *, max_results: int = 3, timeout: float = 20.0) -> tuple[str, str]:
    """Fetch arXiv results; return (source_url, formatted content).

    Network I/O is isolated here so parsing/formatting stay pure. Raises
    ArxivError on any network or parsing failure (including rate limiting).
    """
    import httpx

    clean = normalize_query(query)
    params: dict[str, str | int] = {
        "search_query": f"all:{clean}",
        "start": 0,
        "max_results": max(1, max_results),
    }
    try:
        resp = httpx.get(
            ARXIV_API, params=params, timeout=timeout,
            headers={"User-Agent": USER_AGENT}, follow_redirects=True,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        raise ArxivError(f"could not fetch arXiv results: {exc}") from exc
    papers = parse_arxiv_atom(resp.text)
    page_url = papers[0].url or f"https://arxiv.org/search/?query={clean.replace(' ', '+')}"
    return page_url, format_papers(papers)
