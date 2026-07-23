"""LLM_Provider: isolates every model call behind a small interface.

Two capabilities:
- ``decide_action``: ask the model to choose the next agent action (structured).
- ``generate``: free-form text generation (used for synthesis).
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
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


def _recover_from_obj(obj: Any) -> dict[str, Any] | None:
    """Recover a decision from one decoded object, including error wrappers."""
    decision = _decision_from_obj(obj)
    if decision is not None:
        return decision
    if not isinstance(obj, dict):
        return None
    error = obj.get("error")
    failed_generation = error.get("failed_generation") if isinstance(error, dict) else None
    if isinstance(failed_generation, str) and failed_generation:
        return _recover_from_failed_generation(failed_generation)
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
        recovered = _recover_from_obj(body)
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

    # Shapes 2/3: decode every JSON object embedded in the text. ``raw_decode``
    # handles an API-error prefix such as "LLM HTTP 400: " while a regex cannot
    # reliably distinguish braces inside an escaped ``failed_generation`` value.
    decoder = json.JSONDecoder()
    for offset, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[offset:])
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        decision = _recover_from_obj(parsed)
        if decision is not None:
            return decision
    return None


def _chat_message(data: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the first assistant message or raise a stable protocol error."""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMError("LLM returned an invalid response: choices must be a non-empty list")
    first = choices[0]
    if not isinstance(first, Mapping):
        raise LLMError("LLM returned an invalid response: choice must be an object")
    message = first.get("message")
    if not isinstance(message, Mapping):
        raise LLMError("LLM returned an invalid response: message must be an object")
    return message


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
        try:
            data = resp.json()
        except (TypeError, ValueError) as exc:
            raise LLMError("LLM returned malformed JSON") from exc
        if not isinstance(data, Mapping):
            raise LLMError("LLM returned an invalid response: root must be an object")
        if self._usage is not None:
            usage = data.get("usage")
            if usage is not None and not isinstance(usage, Mapping):
                raise LLMError("LLM returned an invalid response: usage must be an object")
            self._usage.record(usage)
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

        message = _chat_message(data)
        tool_calls = message.get("tool_calls") or []
        if not isinstance(tool_calls, list):
            raise LLMError("LLM returned an invalid response: tool_calls must be a list")
        if tool_calls:
            call = tool_calls[0]
            if not isinstance(call, Mapping):
                raise LLMError("LLM returned an invalid response: tool call must be an object")
            fn = call.get("function", {})
            if not isinstance(fn, Mapping):
                raise LLMError("LLM returned an invalid response: function must be an object")
            name = fn.get("name", "")
            if not isinstance(name, str):
                raise LLMError("LLM returned an invalid response: function name must be text")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except (json.JSONDecodeError, TypeError):
                args = {}
            if not isinstance(args, dict):
                args = {}
            return {"action": name, **args}
        # No tool call: try to parse any JSON content as a fallback.
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            raise LLMError("LLM returned an invalid response: content must be text or null")
        recovered = _recover_from_failed_generation(content or "")
        if recovered is not None:
            return recovered
        return {"action": "__no_tool_call__", "raw": content}

    def generate(self, messages: Sequence[Message]) -> str:
        message = _chat_message(self._chat(messages))
        content = message.get("content")
        if not isinstance(content, str):
            raise LLMError("LLM returned an invalid response: content must be text")
        return content

    def generate_stream(self, messages: Sequence[Message]) -> Iterator[str]:
        """Yield text chunks as they arrive (Server-Sent Events streaming).

        Usage totals are recorded if the final chunk includes a usage block.
        Invalid JSON or an invalid OpenAI-compatible schema raises ``LLMError``
        instead of leaking ``ValueError``, ``KeyError`` or ``AttributeError``.
        """
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        try:
            with self._client.stream("POST", "/chat/completions", json=payload) as resp:
                if resp.status_code >= 400:
                    body = resp.read().decode("utf-8", "replace")
                    if is_transient_status(resp.status_code):
                        hint = parse_retry_after(resp.headers.get("Retry-After")) or \
                            parse_retry_after_from_body(body)
                        raise TransientLLMError(
                            f"LLM transient HTTP {resp.status_code}", retry_after=hint
                        )
                    raise LLMError(f"LLM HTTP {resp.status_code}: {body[:500]}")
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except (json.JSONDecodeError, TypeError) as exc:
                        raise LLMError("LLM returned malformed streaming JSON") from exc
                    if not isinstance(chunk, Mapping):
                        raise LLMError("LLM returned an invalid streaming response")
                    usage = chunk.get("usage")
                    if usage is not None and not isinstance(usage, Mapping):
                        raise LLMError(
                            "LLM returned an invalid streaming response: usage must be an object"
                        )
                    if self._usage is not None:
                        self._usage.record(usage)
                    choices = chunk.get("choices") or []
                    if not isinstance(choices, list):
                        raise LLMError(
                            "LLM returned an invalid streaming response: choices must be a list"
                        )
                    if not choices:
                        continue
                    choice = choices[0]
                    if not isinstance(choice, Mapping):
                        raise LLMError(
                            "LLM returned an invalid streaming response: choice must be an object"
                        )
                    delta = choice.get("delta") or {}
                    if not isinstance(delta, Mapping):
                        raise LLMError(
                            "LLM returned an invalid streaming response: delta must be an object"
                        )
                    piece = delta.get("content")
                    if piece is not None and not isinstance(piece, str):
                        raise LLMError(
                            "LLM returned an invalid streaming response: content must be text"
                        )
                    if piece:
                        yield piece
        except self._httpx.TimeoutException as exc:
            raise TransientLLMError(f"LLM request timed out: {exc}") from exc
        except self._httpx.HTTPError as exc:
            raise TransientLLMError(f"LLM connection error: {exc}") from exc
