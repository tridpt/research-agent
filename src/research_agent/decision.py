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

    if action is ActionType.CALCULATE:
        expr = raw.get("expression")
        if not isinstance(expr, str) or not expr.strip():
            return InvalidDecision(reason="CALCULATE requires a non-empty 'expression'")
        return AgentDecision(action=action, expression=expr.strip(), reasoning=reasoning)

    if action is ActionType.NOW:
        return AgentDecision(action=ActionType.NOW, reasoning=reasoning)

    if action is ActionType.READ_PDF:
        path = raw.get("path")
        if not isinstance(path, str) or not path.strip():
            return InvalidDecision(reason="READ_PDF requires a non-empty 'path'")
        return AgentDecision(action=action, path=path.strip(), reasoning=reasoning)

    if action is ActionType.GET_WEATHER:
        location = raw.get("location")
        if not isinstance(location, str) or not location.strip():
            return InvalidDecision(reason="GET_WEATHER requires a non-empty 'location'")
        return AgentDecision(action=action, location=location.strip(), reasoning=reasoning)

    if action is ActionType.GET_STOCK:
        symbol = raw.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            return InvalidDecision(reason="GET_STOCK requires a non-empty 'symbol'")
        return AgentDecision(action=action, symbol=symbol.strip(), reasoning=reasoning)

    if action is ActionType.GET_WIKIPEDIA:
        topic = raw.get("topic")
        if not isinstance(topic, str) or not topic.strip():
            return InvalidDecision(reason="GET_WIKIPEDIA requires a non-empty 'topic'")
        return AgentDecision(action=action, topic=topic.strip(), reasoning=reasoning)

    if action is ActionType.ARXIV_SEARCH:
        query = raw.get("query")
        if not isinstance(query, str) or not query.strip():
            return InvalidDecision(reason="ARXIV_SEARCH requires a non-empty 'query'")
        return AgentDecision(action=action, paper_query=query.strip(), reasoning=reasoning)

    if action is ActionType.CONVERT:
        expr = raw.get("expression")
        if not isinstance(expr, str) or not expr.strip():
            return InvalidDecision(reason="CONVERT requires a non-empty 'expression'")
        return AgentDecision(action=action, conversion=expr.strip(), reasoning=reasoning)

    if action is ActionType.GET_NEWS:
        query = raw.get("query")
        if not isinstance(query, str) or not query.strip():
            return InvalidDecision(reason="GET_NEWS requires a non-empty 'query'")
        return AgentDecision(action=action, news_query=query.strip(), reasoning=reasoning)

    if action is ActionType.GET_GITHUB:
        repo = raw.get("repo")
        if not isinstance(repo, str) or not repo.strip():
            return InvalidDecision(reason="GET_GITHUB requires a non-empty 'repo'")
        return AgentDecision(action=action, repo=repo.strip(), reasoning=reasoning)

    # FINISH needs no extra parameters.
    return AgentDecision(action=ActionType.FINISH, reasoning=reasoning)
