"""Test doubles for the I/O boundary."""
from __future__ import annotations

from collections.abc import Sequence

from research_agent.fetch_tool import FetchOutcome
from research_agent.llm import Message, RawDecision, ToolSpec
from research_agent.models import Source
from research_agent.search_tool import SearchOutcome


class ScriptedLLM:
    """Returns a queued sequence of raw decisions, then 'finish'; canned text."""

    def __init__(self, decisions: list[RawDecision], text: str = "Synthesized answer [https://a.com/x]") -> None:
        self._decisions = list(decisions)
        self._text = text
        self.decide_calls = 0
        self.generate_calls = 0

    def decide_action(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> RawDecision:
        self.decide_calls += 1
        if self._decisions:
            return self._decisions.pop(0)
        return {"action": "finish"}

    def generate(self, messages: Sequence[Message]) -> str:
        self.generate_calls += 1
        return self._text


class FakeSearch:
    def __init__(self, outcome: SearchOutcome | None = None) -> None:
        self._outcome = outcome or SearchOutcome(results=())
        self.queries: list[str] = []

    def search(self, query: str) -> SearchOutcome:
        self.queries.append(query)
        return self._outcome


class FakeFetch:
    def __init__(self, mapping: dict[str, FetchOutcome] | None = None) -> None:
        self._mapping = mapping or {}
        self.urls: list[str] = []

    def fetch(self, url: str) -> FetchOutcome:
        self.urls.append(url)
        if url in self._mapping:
            return self._mapping[url]
        return FetchOutcome(source=Source(url=url, content=f"content of {url}", fetched_at=0.0))
