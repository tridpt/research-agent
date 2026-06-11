"""Custom exception types used to distinguish recoverable from fatal errors."""
from __future__ import annotations


class ResearchAgentError(Exception):
    """Base class for all application errors."""


class ConfigError(ResearchAgentError):
    """Raised when required configuration (e.g. API key) is missing or invalid."""


class ReportWriteError(ResearchAgentError):
    """Raised when the final Markdown report cannot be written to disk."""


class LLMError(ResearchAgentError):
    """Raised when the LLM provider fails after exhausting retries."""
