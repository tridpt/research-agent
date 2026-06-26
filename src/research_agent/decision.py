"""Pure parsing of the LLM's raw action choice into a typed decision."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .models import ActionType, AgentDecision, InvalidDecision
from .tool_registry import INFO_TOOL_BY_ACTION, NOTE_TOOL_BY_ACTION

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

    if action is ActionType.NOW:
        return AgentDecision(action=ActionType.NOW, reasoning=reasoning)

    if action is ActionType.READ_PDF:
        path = raw.get("path")
        if not isinstance(path, str) or not path.strip():
            return InvalidDecision(reason="READ_PDF requires a non-empty 'path'")
        return AgentDecision(action=action, path=path.strip(), reasoning=reasoning)

    # Local note tools (calculate, convert) share one validation shape.
    note_tool = NOTE_TOOL_BY_ACTION.get(action)
    if note_tool is not None:
        value = raw.get(note_tool.schema_param)
        if not isinstance(value, str) or not value.strip():
            return InvalidDecision(
                reason=f"{note_tool.name.upper()} requires a non-empty '{note_tool.schema_param}'"
            )
        return AgentDecision(
            action=action, reasoning=reasoning, **{note_tool.arg_field: value.strip()}
        )

    # Single-argument external info tools (weather, stock, Wikipedia, arXiv,
    # news, GitHub) all share one validation shape, defined in the registry.
    info_tool = INFO_TOOL_BY_ACTION.get(action)
    if info_tool is not None:
        value = raw.get(info_tool.schema_param)
        if not isinstance(value, str) or not value.strip():
            return InvalidDecision(
                reason=f"{info_tool.name.upper()} requires a non-empty '{info_tool.schema_param}'"
            )
        return AgentDecision(
            action=action, reasoning=reasoning, **{info_tool.arg_field: value.strip()}
        )

    # FINISH needs no extra parameters.
    return AgentDecision(action=ActionType.FINISH, reasoning=reasoning)
