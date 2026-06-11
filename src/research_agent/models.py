"""Core data models.

All value objects are immutable (`frozen=True`) so the deterministic core
functions are easy to reason about and test. `SessionState` is mutable because
it accumulates progress across the agent loop.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------
class ActionType(Enum):
    SEARCH = "search"
    READ = "read"
    FINISH = "finish"
    CALCULATE = "calculate"
    NOW = "now"


class TransitionKind(Enum):
    CONTINUE = "continue"
    SYNTHESIZE = "synthesize"


class TraceEventType(Enum):
    ACTION_SELECTED = "action_selected"
    ROUND_COMPLETED = "round_completed"
    TOOL_ERROR = "tool_error"


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ResearchBudget:
    """Hard limits that guarantee a Session always terminates."""

    max_rounds: int = 8
    max_sources: int = 12
    max_seconds: float = 180.0


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    search_api_key: str | None = None
    blocked_domains: frozenset[str] = frozenset()
    per_source_char_limit: int = 12000
    max_llm_attempts: int = 3
    budget: ResearchBudget = field(default_factory=ResearchBudget)
    output_path: Path | None = None
    verbose: bool = False
    # Source-diversity controls.
    min_domains: int = 2          # soft: encourage >= this many distinct domains
    max_per_domain: int = 2       # hard: never collect more than this per domain
    # Fetch cache.
    cache_dir: Path | None = None
    cache_ttl: float = 0.0        # seconds; <=0 means entries never expire


# --------------------------------------------------------------------------
# Tool data
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class Source:
    url: str
    content: str
    fetched_at: float


# --------------------------------------------------------------------------
# Agent decisions
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class AgentDecision:
    action: ActionType
    reasoning: str = ""
    query: str | None = None
    url: str | None = None
    expression: str | None = None


@dataclass(frozen=True)
class InvalidDecision:
    reason: str


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Citation:
    claim_ref: str
    url: str


@dataclass(frozen=True)
class Report:
    question: str
    body_markdown: str
    citations: tuple[Citation, ...] = ()
    sources: tuple[Source, ...] = ()
    no_information: bool = False


# --------------------------------------------------------------------------
# Transition (pure agent-loop control output)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Transition:
    kind: TransitionKind
    reason: str


# --------------------------------------------------------------------------
# Observability
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class TraceEvent:
    type: TraceEventType
    round_index: int
    sources_count: int
    detail: Mapping[str, str] = field(default_factory=dict)
    reasoning: str | None = None


# --------------------------------------------------------------------------
# Mutable session state
# --------------------------------------------------------------------------
@dataclass
class SessionState:
    question: str
    started_at: float
    rounds_used: int = 0
    sources: list[Source] = field(default_factory=list)
    search_results: list[SearchResult] = field(default_factory=list)
    search_history: list[str] = field(default_factory=list)
    last_decision: AgentDecision | None = None
    invalid_decision_streak: int = 0
    failed_urls: set[str] = field(default_factory=set)
    tool_notes: list[str] = field(default_factory=list)
