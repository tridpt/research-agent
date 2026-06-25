"""Optional on-disk cache for LLM responses.

Keyed by a hash of (model, messages, tools), it lets repeated identical prompts
— common across reflection iterations, multi-agent sub-questions, and re-runs of
the same question — reuse a prior response instead of paying for another call.

Opt-in (default off) because caching a decision can change loop dynamics; the
key includes the full message context so only truly identical states reuse a
response.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from .llm import LLMProvider, Message, RawDecision, ToolSpec


def llm_cache_key(model: str, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()) -> str:
    """Pure: a stable filename-safe key for a prompt."""
    payload = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "tools": [dict(t) for t in tools],
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class LLMResponseCache:
    """File-based cache for decisions and generated text (separate namespaces)."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def _path(self, namespace: str, key: str) -> Path:
        return self.directory / f"{namespace}-{key}.json"

    def get(self, namespace: str, key: str) -> Any | None:
        path = self._path(namespace, key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))["value"]
        except (OSError, ValueError, KeyError):
            return None

    def put(self, namespace: str, key: str, value: Any) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._path(namespace, key).write_text(
                json.dumps({"value": value}, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            # Caching is best-effort; a write failure must not break a run.
            pass


class CachingLLMProvider:
    """Wraps an LLMProvider, serving cached decisions/text for identical prompts."""

    def __init__(self, inner: LLMProvider, cache: LLMResponseCache, model: str) -> None:
        self._inner = inner
        self._cache = cache
        self._model = model
        self.hits = 0
        self.misses = 0

    def decide_action(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> RawDecision:
        key = llm_cache_key(self._model, messages, tools)
        cached = self._cache.get("decision", key)
        if isinstance(cached, Mapping):
            self.hits += 1
            return cached
        self.misses += 1
        result = self._inner.decide_action(messages, tools)
        if isinstance(result, Mapping):
            self._cache.put("decision", key, dict(result))
        return result

    def generate(self, messages: Sequence[Message]) -> str:
        key = llm_cache_key(self._model, messages)
        cached = self._cache.get("text", key)
        if isinstance(cached, str):
            self.hits += 1
            return cached
        self.misses += 1
        result = self._inner.generate(messages)
        self._cache.put("text", key, result)
        return result

    def generate_stream(self, messages: Sequence[Message]) -> Iterator[str]:
        # Streaming is delegated (not cached) so the UI's live output is intact.
        stream = getattr(self._inner, "generate_stream", None)
        if stream is None:  # pragma: no cover - all real providers implement it
            yield self.generate(messages)
            return
        yield from stream(messages)
