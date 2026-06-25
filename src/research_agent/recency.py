"""Recency detection for time-sensitive questions.

Pure helpers that decide whether a question is asking for current/recent
information and produce a trusted directive nudging the agent toward fresh
sources and the ``now``/``get_news`` tools.
"""
from __future__ import annotations

import re

# Recency cue words in English and Vietnamese.
_RECENCY_TERMS = (
    "latest", "newest", "recent", "recently", "current", "currently", "today",
    "now", "this year", "this month", "up to date", "up-to-date", "as of",
    "breaking", "trend", "trending",
    "mới nhất", "gần đây", "hiện tại", "hiện nay", "bây giờ", "hôm nay",
    "năm nay", "cập nhật", "xu hướng", "mới đây",
)
_YEAR_RE = re.compile(r"\b(20[2-9]\d)\b")


def wants_recency(question: str) -> bool:
    """Pure: True if the question asks for current/recent information.

    Triggers on explicit recency cue words (EN/VI) or a 4-digit year >= 2020.
    """
    text = (question or "").lower()
    if any(term in text for term in _RECENCY_TERMS):
        return True
    return _YEAR_RE.search(text) is not None


def recency_directive() -> str:
    """Pure: a trusted instruction to prioritize fresh, dated information."""
    return (
        "This question is time-sensitive. Prioritize the most recent information: "
        "prefer recently published sources, use the NOW tool to anchor 'today', "
        "consider GET_NEWS for current events, and state the date of any fast-"
        "changing facts so the reader knows how current they are."
    )
