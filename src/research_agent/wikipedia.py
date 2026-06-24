"""Wikipedia lookup tool.

Fetches the lead extract of the best-matching Wikipedia article via the public
MediaWiki API (no API key). Parsing/formatting are pure functions so they can be
unit-tested without any network; the single HTTP call lives behind
``fetch_wikipedia``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# MediaWiki action API; ``generator=search`` resolves a free-text topic to the
# best-matching page and returns its plain-text lead extract in one request.
WIKI_API = "https://{lang}.wikipedia.org/w/api.php"
_DEFAULT_LANG = "en"
# Wikipedia's API policy asks for a descriptive User-Agent.
USER_AGENT = "research-agent/0.1 (https://github.com/tridpt/research-agent)"


class WikipediaError(ValueError):
    """Raised when a topic is invalid or no article could be found."""


@dataclass(frozen=True)
class WikiArticle:
    title: str
    extract: str
    url: str


def normalize_topic(raw: str) -> str:
    """Pure: trim a user-supplied topic; reject empty input."""
    cleaned = (raw or "").strip()
    if not cleaned:
        raise WikipediaError("empty topic")
    return cleaned


def normalize_lang(raw: str | None) -> str:
    """Pure: a safe Wikipedia language subdomain (letters/hyphen only)."""
    cleaned = "".join(ch for ch in (raw or "").strip().lower() if ch.isalpha() or ch == "-")
    return cleaned or _DEFAULT_LANG


def wikipedia_query_params(topic: str) -> dict[str, Any]:
    """Pure: the MediaWiki query parameters for a topic search."""
    return {
        "action": "query",
        "format": "json",
        "prop": "extracts|info",
        "inprop": "url",
        "exintro": 1,
        "explaintext": 1,
        "redirects": 1,
        "generator": "search",
        "gsrsearch": topic,
        "gsrlimit": 1,
    }


def parse_wikipedia_response(payload: Any) -> WikiArticle:
    """Pure: extract the top article from a MediaWiki query response.

    Raises WikipediaError when no page matched or the extract is empty.
    """
    if not isinstance(payload, dict):
        raise WikipediaError("malformed response")
    query = payload.get("query")
    if not isinstance(query, dict):
        raise WikipediaError("no article found")
    pages = query.get("pages")
    if not isinstance(pages, dict) or not pages:
        raise WikipediaError("no article found")
    # Pick the best search hit (lowest "index" that the search generator set).
    candidates = [p for p in pages.values() if isinstance(p, dict)]
    if not candidates:
        raise WikipediaError("no article found")
    candidates.sort(key=lambda p: p.get("index", 1_000_000))
    page = candidates[0]

    title = str(page.get("title") or "").strip()
    extract = str(page.get("extract") or "").strip()
    url = str(page.get("fullurl") or "").strip()
    if not title or not extract:
        raise WikipediaError("article has no usable summary")
    return WikiArticle(title=title, extract=extract, url=url)


def format_article(article: WikiArticle, max_chars: int = 4000) -> str:
    """Pure: a titled, length-capped plain-text block for agent context."""
    extract = article.extract
    if max_chars > 0 and len(extract) > max_chars:
        extract = extract[:max_chars].rstrip() + "…"
    return f"Wikipedia — {article.title}\n\n{extract}"


def fetch_wikipedia(
    topic: str,
    *,
    lang: str | None = None,
    max_chars: int = 4000,
    timeout: float = 15.0,
) -> tuple[str, str]:
    """Fetch a Wikipedia summary; return (article_url, formatted content).

    Network I/O is isolated here so the parser/formatter stay pure. Raises
    WikipediaError on any network or parsing failure.
    """
    import httpx

    clean_topic = normalize_topic(topic)
    clean_lang = normalize_lang(lang)
    url = WIKI_API.format(lang=clean_lang)
    try:
        resp = httpx.get(
            url,
            params=wikipedia_query_params(clean_topic),
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        resp.raise_for_status()
        payload = resp.json()
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        raise WikipediaError(f"could not fetch article: {exc}") from exc
    except ValueError as exc:  # pragma: no cover - invalid JSON
        raise WikipediaError(f"invalid article response: {exc}") from exc

    article = parse_wikipedia_response(payload)
    page_url = article.url or f"https://{clean_lang}.wikipedia.org/wiki/{clean_topic.replace(' ', '_')}"
    return page_url, format_article(article, max_chars)
