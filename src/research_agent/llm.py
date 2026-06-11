"""LLM_Provider: isolates every model call behind a small interface.

Two capabilities:
- ``decide_action``: ask the model to choose the next agent action (structured).
- ``generate``: free-form text generation (used for synthesis).
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from .errors import LLMError

if TYPE_CHECKING:
    from .usage import UsageTracker


@dataclass(frozen=True)
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


# A loose tool spec; the OpenAI-compatible client maps it to the wire format.
ToolSpec = Mapping[str, Any]

# Raw structured decision returned by the model (e.g. a dict of action params).
RawDecision = Mapping[str, Any]


class TransientLLMError(LLMError):
    """A retryable LLM failure (rate limit, timeout, 5xx, connection error).

    May carry a ``retry_after`` hint (seconds) parsed from a Retry-After header.
    """

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def parse_retry_after(value: str | None, now: float | None = None) -> float | None:
    """Pure: interpret a Retry-After header value as a delay in seconds.

    Accepts either an integer number of seconds or an HTTP date. Returns None
    when the value is missing or unparseable; negative delays clamp to 0.
    """
    if not value:
        return None
    value = value.strip()
    # Numeric form: delta-seconds.
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    # HTTP-date form.
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(value)
        if dt is None:
            return None
        import time as _time

        target = dt.timestamp()
        current = now if now is not None else _time.time()
        return max(0.0, target - current)
    except (TypeError, ValueError):
        return None


def parse_retry_after_from_body(body: str | None) -> float | None:
    """Pure: extract a retry delay (seconds) from an error message body.

    Some providers (e.g. Gemini) put the hint in the JSON body rather than the
    Retry-After header, e.g. "Please retry in 7.92s" or "retry after 30s".
    Returns the delay in seconds, or None if not found.
    """
    if not body:
        return None
    m = re.search(r"retry(?:\s+in|\s+after)?\s+(\d+(?:\.\d+)?)\s*(ms|milliseconds|s|seconds?)?",
                  body, re.IGNORECASE)
    if not m:
        return None
    value = float(m.group(1))
    unit = (m.group(2) or "s").lower()
    if unit.startswith("ms") or unit == "milliseconds":
        value /= 1000.0
    return max(0.0, value)


class LLMProvider(Protocol):
    def decide_action(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> RawDecision:
        """Ask the LLM to choose the next action as structured data."""

    def generate(self, messages: Sequence[Message]) -> str:
        """Generate free-form text (used for synthesis)."""


_TRANSIENT_STATUS = {408, 409, 429, 500, 502, 503, 504}


def is_transient_status(status_code: int) -> bool:
    return status_code in _TRANSIENT_STATUS


def _decision_from_obj(obj: Any) -> dict[str, Any] | None:
    """Pure: extract a normalized decision dict from a parsed object.

    Accepts both a direct ``{"action": ...}`` and a wrapped tool-call form like
    ``{"name": "search", "arguments": {"action": ...}}`` or
    ``{"name": "search", "arguments": {"query": ...}}``.
    """
    if not isinstance(obj, dict):
        return None
    if "action" in obj:
        return obj
    # Wrapped tool-call shape: {"name": NAME, "arguments": {...}}
    name = obj.get("name")
    args = obj.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, TypeError):
            args = {}
    if isinstance(args, dict):
        if "action" in args:
            return args
        if isinstance(name, str) and name.lower() in {"search", "read", "finish"}:
            return {"action": name.lower(), **args}
    return None


def _recover_from_failed_generation(text: str) -> dict[str, Any] | None:
    """Pure: recover an intended action from malformed/plain-text tool output.

    Handles shapes some open models emit instead of a proper tool call:
      1. ``<function=search{"query": "..."}>``        (Llama-on-Groq style)
      2. a JSON object ``{"action": "read", ...}``     (plain content)
      3. an error body whose ``failed_generation`` holds either of the above,
         possibly with a wrapper like ``{"name": "JSON", "arguments": {...}}``.
    Returns a normalized decision dict, or None if nothing usable is found.
    """
    if not text:
        return None

    # If this looks like an API error body, pull out failed_generation first
    # (json.loads handles the escaping for us).
    try:
        body = json.loads(text)
        fg = body.get("error", {}).get("failed_generation") if isinstance(body, dict) else None
        if isinstance(fg, str) and fg:
            recovered = _recover_from_failed_generation(fg)
            if recovered is not None:
                return recovered
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass

    # Shape 1: <function=NAME{json-args}>
    m = re.search(r"<function=(\w+)\s*(\{.*?\})\s*>", text, re.DOTALL)
    if m:
        name = m.group(1)
        try:
            args = json.loads(m.group(2))
        except (json.JSONDecodeError, TypeError):
            args = {}
        if isinstance(args, dict):
            return {"action": name, **args}
        return {"action": name}

    # Shapes 2/3: any JSON object in the text that yields a decision.
    for match in re.finditer(r"\{(?:[^{}]|\{[^{}]*\})*\}", text, re.DOTALL):
        try:
            parsed = json.loads(match.group(0))
        except (json.JSONDecodeError, TypeError):
            continue
        decision = _decision_from_obj(parsed)
        if decision is not None:
            return decision
    return None


class OpenAICompatibleProvider:
    """Minimal OpenAI-compatible chat client built on httpx.

    Kept dependency-light and easy to mock in tests.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 60.0,
        usage: UsageTracker | None = None,
    ) -> None:
        import httpx  # imported lazily so unit tests need not install it

        self._model = model
        self._usage = usage
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        self._httpx = httpx

    def _chat(self, messages: Sequence[Message], **extra: Any) -> Mapping[str, Any]:
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            **extra,
        }
        try:
            resp = self._client.post("/chat/completions", json=payload)
        except self._httpx.TimeoutException as exc:
            raise TransientLLMError(f"LLM request timed out: {exc}") from exc
        except self._httpx.HTTPError as exc:
            raise TransientLLMError(f"LLM connection error: {exc}") from exc

        if is_transient_status(resp.status_code):
            # Prefer the Retry-After header; fall back to a hint in the body
            # (e.g. Gemini's "Please retry in 7.9s").
            retry_after = parse_retry_after(resp.headers.get("Retry-After"))
            if retry_after is None:
                retry_after = parse_retry_after_from_body(resp.text)
            raise TransientLLMError(
                f"LLM transient HTTP {resp.status_code}", retry_after=retry_after
            )
        if resp.status_code >= 400:
            raise LLMError(f"LLM HTTP {resp.status_code}: {resp.text[:4000]}")
        data = resp.json()
        if self._usage is not None and isinstance(data, dict):
            self._usage.record(data.get("usage"))
        return data

    def decide_action(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> RawDecision:
        """Choose the next action via native tool-calling.

        Sends the tool schemas and asks the model to call one. Returns a
        normalized dict {"action", ...params} that ``parse_decision`` validates.
        Uses ``tool_choice="auto"`` and recovers gracefully when a model emits a
        tool call as plain text (some open models on Groq do this).
        """
        try:
            data = self._chat(
                messages,
                tools=list(tools),
                tool_choice="auto",
            )
        except LLMError as exc:
            # Some models reply with a tool call as text, causing a 400
            # "tool_use_failed". Recover the intended call from the error body.
            recovered = _recover_from_failed_generation(str(exc))
            if recovered is not None:
                return recovered
            raise

        message = data["choices"][0]["message"]
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            call = tool_calls[0]
            fn = call.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except (json.JSONDecodeError, TypeError):
                args = {}
            if not isinstance(args, dict):
                args = {}
            return {"action": name, **args}
        # No tool call: try to parse any JSON content as a fallback.
        content = message.get("content")
        recovered = _recover_from_failed_generation(content or "")
        if recovered is not None:
            return recovered
        return {"action": "__no_tool_call__", "raw": content}

    def generate(self, messages: Sequence[Message]) -> str:
        data = self._chat(messages)
        return data["choices"][0]["message"]["content"]
