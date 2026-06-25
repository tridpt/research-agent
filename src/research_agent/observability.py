"""Observability: render and emit trace events so users can see the agent think."""
from __future__ import annotations

import sys
from collections.abc import Callable
from typing import TextIO

from .models import TraceEvent, TraceEventType


def format_budget_progress(rounds_used: int, sources_count: int, budget: object) -> str:
    """Pure: a compact progress line against the research budget.

    ``budget`` is any object exposing ``max_rounds`` and ``max_sources``.
    """
    max_rounds = getattr(budget, "max_rounds", 0)
    max_sources = getattr(budget, "max_sources", 0)
    return (
        f"    progress: round {rounds_used}/{max_rounds} · "
        f"sources {sources_count}/{max_sources}"
    )


def render_trace(event: TraceEvent, verbose: bool) -> str:
    """Pure: build a one-line human-readable description of a trace event.

    Always includes the event type and its key identifying fields. The LLM's
    reasoning is only appended when ``verbose`` is True (R10.3).
    """
    detail = event.detail or {}
    if event.type is TraceEventType.ACTION_SELECTED:
        action = detail.get("action", "?")
        if action == "search":
            head = f"[round {event.round_index}] SEARCH query={detail.get('query', '')!r}"
        elif action == "read":
            head = f"[round {event.round_index}] READ url={detail.get('url', '')}"
        else:
            head = f"[round {event.round_index}] {action.upper()}"
    elif event.type is TraceEventType.ROUND_COMPLETED:
        head = f"[round {event.round_index}] done · sources={event.sources_count}"
    else:  # TOOL_ERROR
        head = f"[round {event.round_index}] ERROR {detail.get('error', '')}"

    if verbose and event.reasoning:
        head += f"\n    reasoning: {event.reasoning}"
    return head


class TraceEmitter:
    """Side-effecting sink that prints rendered trace lines to a stream."""

    def __init__(
        self,
        verbose: bool = False,
        stream: TextIO | None = None,
        budget: object | None = None,
    ) -> None:
        self.verbose = verbose
        self._stream = stream if stream is not None else sys.stderr
        self._budget = budget

    def __call__(self, event: TraceEvent) -> None:
        line = render_trace(event, self.verbose)
        if self._budget is not None and event.type is TraceEventType.ROUND_COMPLETED:
            line += "\n" + format_budget_progress(
                event.round_index, event.sources_count, self._budget
            )
        print(line, file=self._stream)


def make_emitter(
    verbose: bool, stream: TextIO | None = None, budget: object | None = None
) -> Callable[[TraceEvent], None]:
    return TraceEmitter(verbose=verbose, stream=stream, budget=budget)


class CollectingEmitter:
    """Emitter that stores rendered trace lines and optionally calls a callback.

    Useful for UIs (e.g. Streamlit) that want to display the agent's steps live
    instead of printing to a terminal.
    """

    def __init__(
        self,
        verbose: bool = True,
        on_event: Callable[[str, TraceEvent], None] | None = None,
    ) -> None:
        self.verbose = verbose
        self.lines: list[str] = []
        self._on_event = on_event

    def __call__(self, event: TraceEvent) -> None:
        line = render_trace(event, self.verbose)
        self.lines.append(line)
        if self._on_event is not None:
            self._on_event(line, event)

