"""Pure parsing of the LLM's raw action choice into a typed decision."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .models import ActionType, AgentDecision, InvalidDecision

# A RawDecision is whatever the LLM provider hands back for an action choice:
# typically a dict like {"action": "search", "query": "...", "reasoning": "..."}.
RawDecision = Mapping[str, Any]


def parse_decision(raw: Any) -> AgentDecision | InvalidDecision:
    """Validate a raw LLM response into an AgentDecision or InvalidDecision.

    A decision is valid only when it names a known action and carries the
    parameter required by that action (``query`` for SEARCH, ``url`` for READ).
    """
    if not isinstance(raw, Mapping):
        return InvalidDecision(reason="decision is not an object")

    action_raw = raw.get("action")
    if not isinstance(action_raw, str):
        return InvalidDecision(reason="missing or non-string 'action'")

    try:
        action = ActionType(action_raw.strip().lower())
    except ValueError:
        return InvalidDecision(reason=f"unknown action: {action_raw!r}")

    reasoning = str(raw.get("reasoning", "") or "")

    if action is ActionType.SEARCH:
        query = raw.get("query")
        if not isinstance(query, str) or not query.strip():
            return InvalidDecision(reason="SEARCH requires a non-empty 'query'")
        return AgentDecision(action=action, query=query.strip(), reasoning=reasoning)

    if action is ActionType.READ:
        url = raw.get("url")
        if not isinstance(url, str) or not url.strip():
            return InvalidDecision(reason="READ requires a non-empty 'url'")
        return AgentDecision(action=action, url=url.strip(), reasoning=reasoning)

    # FINISH needs no extra parameters.
    return AgentDecision(action=ActionType.FINISH, reasoning=reasoning)
