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
from .url_safety import public_http_url_error


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
        max_redirects: int = 5,
        url_validator: Callable[[str], str | None] = public_http_url_error,
    ) -> None:
        import httpx

        self._blocked = blocked_domains
        self._limit = per_source_char_limit
        self._extractor = extractor
        self._clock = clock
        self._max_redirects = max_redirects
        self._url_validator = url_validator
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; research-agent/0.1; "
                    "+https://github.com/tridpt/research-agent)"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        self._httpx = httpx

    def fetch(self, url: str) -> FetchOutcome:
        # Check the user blocklist first so blocked hosts never trigger DNS.
        if is_blocked(url, self._blocked):
            return FetchOutcome(blocked=True, error=f"blocked domain: {url}")
        unsafe_reason = self._url_validator(url)
        if unsafe_reason:
            return FetchOutcome(error=f"unsafe URL: {unsafe_reason}")
        try:
            final_url = url
            for redirect_count in range(self._max_redirects + 1):
                resp = self._client.get(final_url)
                if not resp.is_redirect:
                    break
                location = resp.headers.get("Location")
                if not location:
                    return FetchOutcome(error=f"redirect without Location for {final_url}")
                if redirect_count == self._max_redirects:
                    return FetchOutcome(error=f"too many redirects for {url}")
                final_url = str(resp.url.join(location))
                if is_blocked(final_url, self._blocked):
                    return FetchOutcome(blocked=True, error=f"blocked redirect domain: {final_url}")
                unsafe_reason = self._url_validator(final_url)
                if unsafe_reason:
                    return FetchOutcome(error=f"unsafe redirect URL: {unsafe_reason}")
            if resp.status_code >= 400:
                return FetchOutcome(error=f"fetch HTTP {resp.status_code} for {final_url}")
            text = self._extractor(resp.text)
            content = truncate_content(text, self._limit)
            return FetchOutcome(source=Source(url=final_url, content=content, fetched_at=self._clock()))
        except self._httpx.HTTPError as exc:
            return FetchOutcome(error=f"fetch failed for {url}: {exc}")
