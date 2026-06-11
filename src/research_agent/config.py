"""Configuration resolution (Config_Manager).

`resolve_settings` is a pure function: it merges CLI overrides, environment
variables, and defaults (in that precedence order) into an immutable
`Settings`. Reading the real environment happens at the boundary in `cli.py`.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import SupportsFloat, SupportsInt, cast

from .errors import ConfigError
from .models import ResearchBudget, Settings

# Environment variable names.
ENV_API_KEY = "RESEARCH_AGENT_API_KEY"
ENV_BASE_URL = "RESEARCH_AGENT_BASE_URL"
ENV_PROVIDER = "RESEARCH_AGENT_PROVIDER"
ENV_MODEL = "RESEARCH_AGENT_MODEL"
ENV_SEARCH_API_KEY = "RESEARCH_AGENT_SEARCH_API_KEY"
ENV_BLOCKED_DOMAINS = "RESEARCH_AGENT_BLOCKED_DOMAINS"
ENV_MAX_ROUNDS = "RESEARCH_AGENT_MAX_ROUNDS"
ENV_MAX_SOURCES = "RESEARCH_AGENT_MAX_SOURCES"
ENV_MAX_SECONDS = "RESEARCH_AGENT_MAX_SECONDS"
ENV_PER_SOURCE_CHARS = "RESEARCH_AGENT_PER_SOURCE_CHARS"
ENV_MAX_LLM_ATTEMPTS = "RESEARCH_AGENT_MAX_LLM_ATTEMPTS"
ENV_MIN_DOMAINS = "RESEARCH_AGENT_MIN_DOMAINS"
ENV_MAX_PER_DOMAIN = "RESEARCH_AGENT_MAX_PER_DOMAIN"
ENV_CACHE_DIR = "RESEARCH_AGENT_CACHE_DIR"
ENV_CACHE_TTL = "RESEARCH_AGENT_CACHE_TTL"

# Maps an optional setting key -> the env var that supplies it.
_ENV_FOR = {
    "base_url": ENV_BASE_URL,
    "provider": ENV_PROVIDER,
    "model": ENV_MODEL,
    "search_api_key": ENV_SEARCH_API_KEY,
    "blocked_domains": ENV_BLOCKED_DOMAINS,
    "per_source_char_limit": ENV_PER_SOURCE_CHARS,
    "max_llm_attempts": ENV_MAX_LLM_ATTEMPTS,
    "max_rounds": ENV_MAX_ROUNDS,
    "max_sources": ENV_MAX_SOURCES,
    "max_seconds": ENV_MAX_SECONDS,
    "min_domains": ENV_MIN_DOMAINS,
    "max_per_domain": ENV_MAX_PER_DOMAIN,
    "cache_dir": ENV_CACHE_DIR,
    "cache_ttl": ENV_CACHE_TTL,
}


@dataclass(frozen=True)
class Defaults:
    """Finite default values for every optional setting."""

    base_url: str = "https://api.openai.com/v1"
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    per_source_char_limit: int = 12000
    max_llm_attempts: int = 3
    max_rounds: int = 8
    max_sources: int = 12
    max_seconds: float = 180.0
    min_domains: int = 2
    max_per_domain: int = 2
    cache_ttl: float = 0.0


DEFAULTS = Defaults()


def _resolve(key: str, cli: Mapping[str, object], env: Mapping[str, str]) -> object | None:
    """Highest-precedence provided value for an optional ``key`` (CLI > env)."""
    if key in cli and cli[key] is not None:
        return cli[key]
    env_name = _ENV_FOR.get(key)
    if env_name and env.get(env_name) not in (None, ""):
        return env[env_name]
    return None


def _as_int(value: object, fallback: int) -> int:
    return fallback if value is None else int(cast(SupportsInt, value))


def _as_float(value: object, fallback: float) -> float:
    return fallback if value is None else float(cast(SupportsFloat, value))


def _parse_blocked(value: object) -> frozenset[str]:
    if value is None:
        return frozenset()
    if isinstance(value, (set, frozenset, list, tuple)):
        items = list(value)
    else:
        items = str(value).split(",")
    return frozenset(str(d).strip().lower() for d in items if str(d).strip())


def resolve_settings(
    env: Mapping[str, str],
    cli_overrides: Mapping[str, object],
    defaults: Defaults = DEFAULTS,
) -> Settings:
    """Resolve final Settings. Precedence: CLI override > env var > default.

    Raises ConfigError if the required API key is absent.
    """
    api_key = cli_overrides.get("api_key") or env.get(ENV_API_KEY)
    if not api_key:
        raise ConfigError(
            f"Missing required API key. Set {ENV_API_KEY} or pass it explicitly."
        )

    base_url = _resolve("base_url", cli_overrides, env) or defaults.base_url
    provider = _resolve("provider", cli_overrides, env) or defaults.provider
    model = _resolve("model", cli_overrides, env) or defaults.model
    search_api_key = _resolve("search_api_key", cli_overrides, env)
    blocked = _parse_blocked(_resolve("blocked_domains", cli_overrides, env))

    per_source = _as_int(
        _resolve("per_source_char_limit", cli_overrides, env), defaults.per_source_char_limit
    )
    max_attempts = _as_int(
        _resolve("max_llm_attempts", cli_overrides, env), defaults.max_llm_attempts
    )

    budget = ResearchBudget(
        max_rounds=_as_int(_resolve("max_rounds", cli_overrides, env), defaults.max_rounds),
        max_sources=_as_int(_resolve("max_sources", cli_overrides, env), defaults.max_sources),
        max_seconds=_as_float(_resolve("max_seconds", cli_overrides, env), defaults.max_seconds),
    )

    out = cli_overrides.get("output_path")
    output_path = Path(str(out)) if out else None

    min_domains = _as_int(_resolve("min_domains", cli_overrides, env), defaults.min_domains)
    max_per_domain = _as_int(_resolve("max_per_domain", cli_overrides, env), defaults.max_per_domain)
    cache_ttl = _as_float(_resolve("cache_ttl", cli_overrides, env), defaults.cache_ttl)
    cache_raw = _resolve("cache_dir", cli_overrides, env)
    cache_dir = Path(str(cache_raw)) if cache_raw else None

    return Settings(
        api_key=str(api_key),
        base_url=str(base_url),
        provider=str(provider),
        model=str(model),
        search_api_key=str(search_api_key) if search_api_key else None,
        blocked_domains=blocked,
        per_source_char_limit=per_source,
        max_llm_attempts=max_attempts,
        budget=budget,
        output_path=output_path,
        verbose=bool(cli_overrides.get("verbose", False)),
        min_domains=min_domains,
        max_per_domain=max_per_domain,
        cache_dir=cache_dir,
        cache_ttl=cache_ttl,
    )
