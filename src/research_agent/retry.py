"""Retry logic for LLM calls.

The attempt-counting policy is a pure function so it can be property-tested
(Property 9): the first failed call counts as attempt #1, so ``max_attempts``
is an upper bound on the total number of calls.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any

from .errors import LLMError
from .llm import LLMProvider, Message, RawDecision, ToolSpec, TransientLLMError


def should_retry(attempt: int, max_attempts: int) -> bool:
    """Pure: may we make another attempt after ``attempt`` failed calls?

    ``attempt`` is the number of calls already made (>= 1). We retry only while
    fewer than ``max_attempts`` calls have been made.
    """
    return attempt < max_attempts


def next_delay(
    attempt: int,
    base_delay: float,
    retry_after: float | None = None,
    max_delay: float = 60.0,
) -> float:
    """Pure: choose the wait before the next retry.

    Honors a server-provided ``retry_after`` hint when present, otherwise uses
    exponential backoff. The result is clamped to ``[0, max_delay]``.
    """
    if retry_after is not None and retry_after >= 0:
        return min(retry_after, max_delay)
    return min(base_delay * (2 ** (attempt - 1)), max_delay)


def call_with_retry(
    fn: Callable[[], Any],
    max_attempts: int,
    sleep: Callable[[float], None] = time.sleep,
    base_delay: float = 0.5,
) -> Any:
    """Invoke ``fn`` retrying only TransientLLMError, up to ``max_attempts`` calls.

    The first (failed) call is attempt #1. Honors a Retry-After hint carried by
    the error when present. Re-raises the last error once attempts are spent.
    """
    if max_attempts < 1:
        max_attempts = 1
    attempt = 0
    last_exc: Exception | None = None
    while attempt < max_attempts:
        attempt += 1
        try:
            return fn()
        except TransientLLMError as exc:
            last_exc = exc
            if not should_retry(attempt, max_attempts):
                break
            sleep(next_delay(attempt, base_delay, getattr(exc, "retry_after", None)))
    raise LLMError(
        f"LLM call failed after {max_attempts} attempt(s): {last_exc}"
    ) from last_exc


class RetryingLLMProvider:
    """Decorator that adds retry-on-transient-error to any LLMProvider."""

    def __init__(
        self,
        inner: LLMProvider,
        max_attempts: int,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._inner = inner
        self._max_attempts = max_attempts
        self._sleep = sleep

    def decide_action(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> RawDecision:
        return call_with_retry(
            lambda: self._inner.decide_action(messages, tools),
            self._max_attempts,
            self._sleep,
        )

    def generate(self, messages: Sequence[Message]) -> str:
        return call_with_retry(
            lambda: self._inner.generate(messages),
            self._max_attempts,
            self._sleep,
        )
