"""Persistent fetch cache keyed by URL.

A small file-based store so a URL fetched in one session is reused in later
sessions, saving time and bandwidth. ``CachingFetchTool`` wraps any FetchTool
and transparently serves cache hits.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from .fetch_tool import FetchOutcome, FetchTool
from .models import Source


def cache_key(url: str) -> str:
    """Pure: stable filename-safe key for a URL."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def is_fresh(fetched_at: float, ttl_seconds: float, now: float) -> bool:
    """Pure: True if a cache entry is still within its time-to-live.

    A non-positive ttl means entries never expire.
    """
    if ttl_seconds <= 0:
        return True
    return (now - fetched_at) <= ttl_seconds


class FetchCache:
    """File-based cache mapping URL -> fetched Source content."""

    def __init__(self, directory: Path, ttl_seconds: float = 0.0) -> None:
        self.directory = Path(directory)
        self.ttl_seconds = ttl_seconds

    def _path(self, url: str) -> Path:
        return self.directory / f"{cache_key(url)}.json"

    def get(self, url: str, now: float | None = None) -> Source | None:
        path = self._path(url)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        fetched_at = float(data.get("fetched_at", 0.0))
        if not is_fresh(fetched_at, self.ttl_seconds, now if now is not None else time.time()):
            return None
        return Source(url=data["url"], content=data["content"], fetched_at=fetched_at)

    def put(self, source: Source) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            payload = {"url": source.url, "content": source.content, "fetched_at": source.fetched_at}
            self._path(source.url).write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            # Caching is best-effort; a write failure must not break research.
            pass


class CachingFetchTool:
    """Wraps a FetchTool, serving cache hits and storing successful fetches."""

    def __init__(self, inner: FetchTool, cache: FetchCache) -> None:
        self._inner = inner
        self._cache = cache
        self.hits = 0
        self.misses = 0

    def fetch(self, url: str) -> FetchOutcome:
        cached = self._cache.get(url)
        if cached is not None:
            self.hits += 1
            return FetchOutcome(source=cached)
        self.misses += 1
        outcome = self._inner.fetch(url)
        if outcome.ok and outcome.source is not None:
            self._cache.put(outcome.source)
        return outcome
