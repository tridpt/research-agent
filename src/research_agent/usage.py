"""Token usage tracking and cost estimation.

The OpenAI-compatible API returns a ``usage`` object on each response. We
accumulate those tokens in a shared ``UsageTracker`` and can estimate cost from
a simple per-million-token price table.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass
class UsageTracker:
    """Mutable accumulator of token usage across LLM calls in a session."""

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def record(self, usage: Mapping[str, Any] | None) -> None:
        """Add one response's ``usage`` block to the running totals."""
        self.calls += 1
        if not usage:
            return
        self.prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
        self.completion_tokens += int(usage.get("completion_tokens", 0) or 0)


@dataclass(frozen=True)
class Price:
    """Price per 1,000,000 tokens, in USD."""

    prompt_per_m: float
    completion_per_m: float


# Rough public prices (USD per 1M tokens). Free providers like Groq/Gemini
# free tier are effectively $0; included models are for estimation only.
PRICES: dict[str, Price] = {
    "gpt-4o-mini": Price(0.15, 0.60),
    "gpt-4o": Price(2.50, 10.00),
    "gemini-2.5-flash-lite": Price(0.0, 0.0),
    "gemini-2.5-flash": Price(0.0, 0.0),
    "openai/gpt-oss-20b": Price(0.0, 0.0),
    "openai/gpt-oss-120b": Price(0.0, 0.0),
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """Estimate USD cost for the given token counts, or None if model unknown."""
    price = PRICES.get(model)
    if price is None:
        return None
    return (
        prompt_tokens / 1_000_000 * price.prompt_per_m
        + completion_tokens / 1_000_000 * price.completion_per_m
    )


def format_usage(tracker: UsageTracker, model: str) -> str:
    """Pure: a one-line human-readable usage/cost summary."""
    cost = estimate_cost(model, tracker.prompt_tokens, tracker.completion_tokens)
    base = (
        f"{tracker.calls} lệnh gọi · {tracker.total_tokens:,} token "
        f"(vào {tracker.prompt_tokens:,} / ra {tracker.completion_tokens:,})"
    )
    if cost is None:
        return base + " · chi phí: không rõ"
    if cost == 0:
        return base + " · chi phí: miễn phí"
    return base + f" · ước tính ~${cost:.4f}"
