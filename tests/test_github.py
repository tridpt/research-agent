"""Tests for the GitHub tool: repo parsing, formatting, and wiring."""
from __future__ import annotations

import pytest

from research_agent.decision import parse_decision
from research_agent.github import (
    GitHubError,
    format_repo,
    normalize_repo,
    parse_release,
    parse_repo,
)
from research_agent.models import ActionType, AgentDecision
from research_agent.tools import TOOL_SCHEMAS

_REPO = {
    "full_name": "python/cpython",
    "description": "The Python programming language",
    "stargazers_count": 73408,
    "forks_count": 34764,
    "open_issues_count": 9410,
    "language": "Python",
    "license": {"spdx_id": "NOASSERTION"},
    "html_url": "https://github.com/python/cpython",
}


def test_normalize_repo_accepts_owner_name_and_urls() -> None:
    assert normalize_repo("python/cpython") == "python/cpython"
    assert normalize_repo("https://github.com/python/cpython") == "python/cpython"
    assert normalize_repo("https://github.com/python/cpython/tree/main") == "python/cpython"
    assert normalize_repo("python/cpython.git") == "python/cpython"


def test_normalize_repo_rejects_invalid() -> None:
    with pytest.raises(GitHubError):
        normalize_repo("not-a-repo")
    with pytest.raises(GitHubError):
        normalize_repo("")


def test_parse_repo_extracts_fields_and_drops_noassertion_license() -> None:
    info = parse_repo(_REPO)
    assert info.full_name == "python/cpython"
    assert info.stars == 73408
    assert info.language == "Python"
    assert info.license == ""  # NOASSERTION is dropped


def test_parse_repo_keeps_real_license() -> None:
    payload = {**_REPO, "license": {"spdx_id": "MIT"}}
    assert parse_repo(payload).license == "MIT"


def test_parse_repo_missing_name_raises() -> None:
    with pytest.raises(GitHubError):
        parse_repo({"description": "x"})


def test_parse_release_handles_present_and_absent() -> None:
    assert parse_release({"tag_name": "v3.13.0", "published_at": "2024-10-07T00:00:00Z"}) == "v3.13.0 (2024-10-07)"
    assert parse_release({}) == ""


def test_format_repo_includes_stats() -> None:
    out = format_repo(parse_repo(_REPO))
    assert "GitHub — python/cpython" in out
    assert "73408 stars" in out
    assert "Python" in out


def test_parse_decision_accepts_get_github() -> None:
    decision = parse_decision({"action": "get_github", "repo": "python/cpython"})
    assert isinstance(decision, AgentDecision)
    assert decision.action is ActionType.GET_GITHUB
    assert decision.repo == "python/cpython"


def test_get_github_tool_is_advertised() -> None:
    assert "get_github" in {t["function"]["name"] for t in TOOL_SCHEMAS}
