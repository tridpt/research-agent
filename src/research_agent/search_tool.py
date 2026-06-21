"""Search_Tool: web search behind a small interface.

Returns a SearchOutcome that either carries results or a descriptive error,
so a failed search never aborts the session.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from .models import SearchResult
from .source_quality import rank_search_results


@dataclass(frozen=True)
class SearchOutcome:
    results: tuple[SearchResult, ...] = ()
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class SearchTool(Protocol):
    def search(self, query: str) -> SearchOutcome:
        ...


def parse_search_results(payload: Any) -> tuple[SearchResult, ...]:
    """Pure: map a generic search-API JSON payload into SearchResult tuples.

    Accepts a list of dicts with title/url/snippet (or common aliases).
    """
    items: Sequence[Any]
    if isinstance(payload, dict):
        items = payload.get("results") or payload.get("organic") or payload.get("data") or []
    elif isinstance(payload, list):
        items = payload
    else:
        items = []

    out: list[SearchResult] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        url = it.get("url") or it.get("link") or it.get("href") or ""
        if not url:
            continue
        title = it.get("title") or it.get("name") or url
        snippet = (
            it.get("snippet")
            or it.get("description")
            or it.get("content")
            or it.get("body")
            or ""
        )
        out.append(SearchResult(title=str(title), url=str(url), snippet=str(snippet)))
    return rank_search_results(out)


class HttpSearchTool:
    """Search tool backed by a configurable OpenAI-style/SerpAPI-style endpoint."""

    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        query_param: str = "q",
    ) -> None:
        import httpx

        self._endpoint = endpoint
        self._query_param = query_param
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(headers=headers, timeout=timeout)
        self._httpx = httpx

    def search(self, query: str) -> SearchOutcome:
        try:
            resp = self._client.get(self._endpoint, params={self._query_param: query})
            if resp.status_code >= 400:
                return SearchOutcome(error=f"search HTTP {resp.status_code}")
            return SearchOutcome(results=parse_search_results(resp.json()))
        except self._httpx.HTTPError as exc:
            return SearchOutcome(error=f"search failed: {exc}")
        except ValueError as exc:  # JSON decode
            return SearchOutcome(error=f"search returned invalid JSON: {exc}")


class DuckDuckGoSearchTool:
    """Free web search via DuckDuckGo (no API key required).

    Backed by the ``ddgs`` package. A ``searcher`` callable can be injected for
    testing so no network call is needed.
    """

    def __init__(
        self,
        max_results: int = 8,
        region: str = "wt-wt",
        searcher: Callable[[str, int, str], list[dict]] | None = None,
    ) -> None:
        self._max_results = max_results
        self._region = region
        self._searcher = searcher or self._default_searcher

    @staticmethod
    def _default_searcher(query: str, max_results: int, region: str) -> list[dict]:
        from ddgs import DDGS

        with DDGS() as ddgs:
            return list(ddgs.text(query, region=region, max_results=max_results))

    def search(self, query: str) -> SearchOutcome:
        try:
            raw = self._searcher(query, self._max_results, self._region)
        except Exception as exc:  # noqa: BLE001 - any provider error is recoverable
            return SearchOutcome(error=f"duckduckgo search failed: {exc}")
        return SearchOutcome(results=parse_search_results(raw))


class TavilySearchTool:
    """Web search via the Tavily API (AI-oriented search; requires an API key)."""

    ENDPOINT = "https://api.tavily.com/search"

    def __init__(self, api_key: str, max_results: int = 8, timeout: float = 30.0) -> None:
        import httpx

        self._api_key = api_key
        self._max_results = max_results
        self._client = httpx.Client(timeout=timeout)
        self._httpx = httpx

    def search(self, query: str) -> SearchOutcome:
        try:
            resp = self._client.post(
                self.ENDPOINT,
                json={
                    "api_key": self._api_key,
                    "query": query,
                    "max_results": self._max_results,
                },
            )
            if resp.status_code >= 400:
                return SearchOutcome(error=f"tavily HTTP {resp.status_code}")
            return SearchOutcome(results=parse_search_results(resp.json()))
        except self._httpx.HTTPError as exc:
            return SearchOutcome(error=f"tavily search failed: {exc}")
        except ValueError as exc:
            return SearchOutcome(error=f"tavily returned invalid JSON: {exc}")


class FallbackSearchTool:
    """Try multiple search providers in order until one returns results.

    A provider is considered failed if it errors OR returns zero results, in
    which case the next provider is tried. The last provider's outcome is
    returned if all fail, so the session still continues gracefully.
    """

    def __init__(self, providers: Sequence[SearchTool]) -> None:
        if not providers:
            raise ValueError("FallbackSearchTool requires at least one provider")
        self._providers = list(providers)

    def search(self, query: str) -> SearchOutcome:
        last = SearchOutcome(error="no search provider produced results")
        errors: list[str] = []
        for provider in self._providers:
            outcome = provider.search(query)
            if outcome.ok and outcome.results:
                return outcome
            last = outcome
            if not outcome.ok and outcome.error:
                errors.append(outcome.error)
        # All providers failed or returned empty; surface a combined error if any.
        if errors and not last.ok:
            return SearchOutcome(error="; ".join(errors))
        return last
