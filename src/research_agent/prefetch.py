"""Parallel prefetching to speed up a research session.

After a search, the agent will usually READ a few of the top results one by
one. Prefetching those pages concurrently warms the fetch cache so the later
READ actions become instant cache hits — cutting wall-clock time without
changing the agent's deterministic decision loop.

``select_prefetch_urls`` (pure) chooses which URLs to warm; ``prefetch_urls``
performs the concurrent fetches via the provided FetchTool (whose caching layer
stores the results as a side effect).
"""
from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from .content import host_of
from .fetch_tool import FetchTool
from .models import SearchResult, Source


def select_prefetch_urls(
    sources: Sequence[Source],
    search_results: Sequence[SearchResult],
    max_per_domain: int,
    limit: int,
    exclude_urls: set[str] | None = None,
) -> tuple[str, ...]:
    """Pure: choose up to ``limit`` unread result URLs worth warming.

    Mirrors the agent's own read constraints: skips already-read URLs, anything
    in ``exclude_urls`` (e.g. previously failed), and never exceeds
    ``max_per_domain`` once existing sources are counted. Prefers spreading
    across new domains first, then fills remaining slots.
    """
    if limit <= 0:
        return ()
    exclude = exclude_urls or set()
    read_urls = {s.url for s in sources}
    domain_counts: dict[str, int] = {}
    for s in sources:
        domain_counts[host_of(s.url)] = domain_counts.get(host_of(s.url), 0) + 1

    chosen: list[str] = []
    seen: set[str] = set()
    for result in search_results:
        if len(chosen) >= limit:
            break
        url = result.url
        if url in read_urls or url in exclude or url in seen:
            continue
        host = host_of(url)
        if domain_counts.get(host, 0) >= max_per_domain:
            continue
        chosen.append(url)
        seen.add(url)
        domain_counts[host] = domain_counts.get(host, 0) + 1
    return tuple(chosen)


def prefetch_urls(fetch: FetchTool, urls: Sequence[str], max_workers: int = 4) -> int:
    """Fetch ``urls`` concurrently (best-effort); return how many succeeded.

    Failures are ignored — prefetching is an optimization, never a correctness
    requirement. The FetchTool's caching wrapper persists successful fetches so
    a later READ of the same URL is a cache hit.
    """
    unique = list(dict.fromkeys(u for u in urls if u))
    if not unique:
        return 0
    workers = max(1, min(max_workers, len(unique)))
    succeeded = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for outcome in executor.map(fetch.fetch, unique):
            if outcome.ok:
                succeeded += 1
    return succeeded
