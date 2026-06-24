"""Recent-news lookup tool (Hacker News via the Algolia API).

Good for current/tech-news questions. The Algolia HN Search API needs no key.
Parsing/formatting are pure; only ``fetch_news`` performs network I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

HN_SEARCH_API = "https://hn.algolia.com/api/v1/search"
HN_ITEM_URL = "https://news.ycombinator.com/item?id={object_id}"
USER_AGENT = "research-agent/0.1 (+https://github.com/tridpt/research-agent)"


class NewsError(ValueError):
    """Raised when a query is invalid or no stories could be parsed."""


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    points: int
    num_comments: int
    created_at: str
    discussion_url: str


def normalize_query(raw: str) -> str:
    """Pure: trim a free-text query; reject empty input."""
    cleaned = " ".join((raw or "").split())
    if not cleaned:
        raise NewsError("empty query")
    return cleaned


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_hn_results(payload: Any, limit: int = 5) -> tuple[NewsItem, ...]:
    """Pure: parse a Hacker News Algolia search response into news items."""
    if not isinstance(payload, dict):
        raise NewsError("malformed response")
    hits = payload.get("hits")
    if not isinstance(hits, list) or not hits:
        raise NewsError("no stories found")
    items: list[NewsItem] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        title = str(hit.get("title") or hit.get("story_title") or "").strip()
        if not title:
            continue
        object_id = str(hit.get("objectID") or "").strip()
        discussion = HN_ITEM_URL.format(object_id=object_id) if object_id else ""
        items.append(
            NewsItem(
                title=title,
                url=str(hit.get("url") or discussion or "").strip(),
                points=_as_int(hit.get("points")),
                num_comments=_as_int(hit.get("num_comments")),
                created_at=str(hit.get("created_at") or "").strip()[:10],
                discussion_url=discussion,
            )
        )
        if len(items) >= max(1, limit):
            break
    if not items:
        raise NewsError("no stories found")
    return tuple(items)


def format_news(items: tuple[NewsItem, ...]) -> str:
    """Pure: a readable plain-text block of news stories."""
    blocks = ["Recent stories (Hacker News):"]
    for i, item in enumerate(items, start=1):
        meta = f"{item.points} points · {item.num_comments} comments · {item.created_at}"
        link = item.url or item.discussion_url
        blocks.append(f"{i}. {item.title}\n   {meta}\n   {link}")
    return "\n".join(blocks)


def fetch_news(query: str, *, limit: int = 5, timeout: float = 15.0) -> tuple[str, str]:
    """Fetch recent stories; return (source_url, formatted content).

    Network I/O is isolated here so parsing/formatting stay pure. Raises
    NewsError on any network or parsing failure.
    """
    import httpx

    clean = normalize_query(query)
    params = {"query": clean, "tags": "story"}
    try:
        resp = httpx.get(
            HN_SEARCH_API, params=params, timeout=timeout,
            headers={"User-Agent": USER_AGENT}, follow_redirects=True,
        )
        resp.raise_for_status()
        payload = resp.json()
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        raise NewsError(f"could not fetch news: {exc}") from exc
    except ValueError as exc:  # pragma: no cover - invalid JSON
        raise NewsError(f"invalid news response: {exc}") from exc
    items = parse_hn_results(payload, limit=limit)
    page_url = f"https://hn.algolia.com/?q={clean.replace(' ', '+')}"
    return page_url, format_news(items)
