"""PubMed biomedical-literature lookup tool.

Searches PubMed via NCBI's public E-utilities (no API key) and returns the top
matching articles' titles, authors, journal, and publication date. This
complements ``arxiv`` (physics/CS preprints) and ``crossref`` (general scholarly
works) with peer-reviewed biomedical/clinical literature.

Two HTTP calls are needed (``esearch`` -> PMIDs, then ``esummary`` -> metadata);
both live behind ``fetch_pubmed`` while all parsing/formatting stay pure so they
can be unit-tested without any network.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# NCBI E-utilities. ``esearch`` resolves a free-text query to PubMed IDs (PMIDs);
# ``esummary`` returns document summaries (title, authors, journal, date).
ESEARCH_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
ARTICLE_URL = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
# NCBI asks callers to identify their tool in requests.
TOOL_NAME = "research-agent"
USER_AGENT = "research-agent/0.1 (+https://github.com/tridpt/research-agent)"


class PubMedError(ValueError):
    """Raised when a query is invalid or no articles could be parsed."""


@dataclass(frozen=True)
class PubMedArticle:
    pmid: str
    title: str
    authors: tuple[str, ...]
    journal: str
    pubdate: str
    url: str


def normalize_query(raw: str) -> str:
    """Pure: collapse whitespace in a free-text query; reject empty input."""
    cleaned = " ".join((raw or "").split())
    if not cleaned:
        raise PubMedError("empty query")
    return cleaned


def esearch_params(query: str, max_results: int = 3) -> dict[str, Any]:
    """Pure: the esearch query parameters resolving a topic to PMIDs."""
    return {
        "db": "pubmed",
        "term": query,
        "retmax": max(1, max_results),
        "retmode": "json",
        "sort": "relevance",
        "tool": TOOL_NAME,
    }


def esummary_params(pmids: tuple[str, ...]) -> dict[str, Any]:
    """Pure: the esummary query parameters for a set of PMIDs."""
    return {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
        "tool": TOOL_NAME,
    }


def parse_esearch(payload: Any) -> tuple[str, ...]:
    """Pure: extract the list of PMIDs from an esearch JSON response.

    Raises PubMedError when the response is malformed or no article matched.
    """
    if not isinstance(payload, dict):
        raise PubMedError("malformed search response")
    result = payload.get("esearchresult")
    if not isinstance(result, dict):
        raise PubMedError("no articles found")
    idlist = result.get("idlist")
    if not isinstance(idlist, list):
        raise PubMedError("no articles found")
    pmids = tuple(str(i).strip() for i in idlist if str(i).strip())
    if not pmids:
        raise PubMedError("no articles found")
    return pmids


def _parse_authors(raw_authors: Any) -> tuple[str, ...]:
    """Pure: pull author display names out of an esummary ``authors`` list."""
    if not isinstance(raw_authors, list):
        return ()
    names: list[str] = []
    for author in raw_authors:
        if isinstance(author, dict):
            name = str(author.get("name") or "").strip()
            if name:
                names.append(name)
    return tuple(names)


def parse_esummary(payload: Any) -> tuple[PubMedArticle, ...]:
    """Pure: parse an esummary JSON response into articles (order preserved).

    Raises PubMedError when the response is malformed or contains no usable
    article summaries.
    """
    if not isinstance(payload, dict):
        raise PubMedError("malformed summary response")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise PubMedError("no article details found")
    # ``uids`` preserves the requested/ranked order; fall back to dict order.
    uids = result.get("uids")
    keys = uids if isinstance(uids, list) else [k for k in result if k != "uids"]

    articles: list[PubMedArticle] = []
    for key in keys:
        pmid = str(key).strip()
        entry = result.get(pmid)
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "").strip().rstrip(".")
        if not title:
            continue
        journal = str(entry.get("fulljournalname") or entry.get("source") or "").strip()
        pubdate = str(entry.get("pubdate") or "").strip()
        articles.append(
            PubMedArticle(
                pmid=pmid,
                title=title,
                authors=_parse_authors(entry.get("authors")),
                journal=journal,
                pubdate=pubdate,
                url=ARTICLE_URL.format(pmid=pmid),
            )
        )
    if not articles:
        raise PubMedError("no usable article summaries")
    return tuple(articles)


def format_articles(articles: tuple[PubMedArticle, ...]) -> str:
    """Pure: a readable, citation-style plain-text block for agent context."""
    blocks: list[str] = ["PubMed results:"]
    for i, a in enumerate(articles, start=1):
        authors = ", ".join(a.authors[:4]) + (" et al." if len(a.authors) > 4 else "")
        meta = " · ".join(part for part in (authors, a.journal, a.pubdate) if part)
        line = f"{i}. {a.title}"
        if meta:
            line += f"\n   {meta}"
        line += f"\n   PMID {a.pmid} · {a.url}"
        blocks.append(line)
    return "\n\n".join(blocks)


def fetch_pubmed(query: str, *, max_results: int = 3, timeout: float = 20.0) -> tuple[str, str]:
    """Fetch PubMed results; return (source_url, formatted content).

    Performs the two-step E-utilities flow (esearch -> esummary) with network
    I/O isolated here so parsing/formatting stay pure. Raises PubMedError on any
    network or parsing failure (including rate limiting).
    """
    import httpx

    clean = normalize_query(query)
    headers = {"User-Agent": USER_AGENT}
    try:
        search_resp = httpx.get(
            ESEARCH_API,
            params=esearch_params(clean, max_results),
            timeout=timeout,
            headers=headers,
            follow_redirects=True,
        )
        search_resp.raise_for_status()
        pmids = parse_esearch(search_resp.json())

        summary_resp = httpx.get(
            ESUMMARY_API,
            params=esummary_params(pmids),
            timeout=timeout,
            headers=headers,
            follow_redirects=True,
        )
        summary_resp.raise_for_status()
        articles = parse_esummary(summary_resp.json())
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        raise PubMedError(f"could not fetch PubMed results: {exc}") from exc
    except ValueError as exc:
        # ValueError covers both invalid JSON and our own PubMedError; re-raise
        # PubMedError unchanged and wrap bare JSON decode errors.
        if isinstance(exc, PubMedError):
            raise
        raise PubMedError(f"invalid PubMed response: {exc}") from exc

    page_url = articles[0].url or f"https://pubmed.ncbi.nlm.nih.gov/?term={clean.replace(' ', '+')}"
    return page_url, format_articles(articles)
