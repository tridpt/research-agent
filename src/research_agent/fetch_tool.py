"""Fetch_Tool: download a URL and extract its main text as a Source.

Blocked domains are skipped before any network call. Network/HTTP failures are
captured as a descriptive error so the session can continue.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from .content import is_blocked, truncate_content
from .models import Source


@dataclass(frozen=True)
class FetchOutcome:
    source: Source | None = None
    error: str | None = None
    blocked: bool = False

    @property
    def ok(self) -> bool:
        return self.source is not None


class FetchTool(Protocol):
    def fetch(self, url: str) -> FetchOutcome:
        ...


def default_extractor(html: str) -> str:
    """Extract main text from HTML using trafilatura, falling back to raw text."""
    try:
        import trafilatura

        extracted = trafilatura.extract(html)
        if extracted:
            return extracted
    except Exception:  # noqa: BLE001 - extraction is best-effort
        pass
    return html


class HttpFetchTool:
    def __init__(
        self,
        blocked_domains: frozenset[str],
        per_source_char_limit: int,
        timeout: float = 30.0,
        extractor: Callable[[str], str] = default_extractor,
        clock: Callable[[], float] = time.time,
    ) -> None:
        import httpx

        self._blocked = blocked_domains
        self._limit = per_source_char_limit
        self._extractor = extractor
        self._clock = clock
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; research-agent/0.1; "
                    "+https://github.com/your-username/research-agent)"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        self._httpx = httpx

    def fetch(self, url: str) -> FetchOutcome:
        # Enforce the blocklist BEFORE any network call (Property 3 / R5.6).
        if is_blocked(url, self._blocked):
            return FetchOutcome(blocked=True, error=f"blocked domain: {url}")
        try:
            resp = self._client.get(url)
            if resp.status_code >= 400:
                return FetchOutcome(error=f"fetch HTTP {resp.status_code} for {url}")
            text = self._extractor(resp.text)
            content = truncate_content(text, self._limit)
            return FetchOutcome(source=Source(url=url, content=content, fetched_at=self._clock()))
        except self._httpx.HTTPError as exc:
            return FetchOutcome(error=f"fetch failed for {url}: {exc}")
