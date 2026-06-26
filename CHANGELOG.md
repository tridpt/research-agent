# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-26

First public release: an autonomous CLI/Web research agent that searches the
web over multiple rounds, reads sources, and synthesizes a cited Markdown
report. Works with any OpenAI-compatible LLM (Groq, Gemini, OpenAI, Ollama).

### Added

- **Agent core**: multi-step loop with a deterministic core (budget enforcement,
  citation validation, content truncation, source-diversity control) separated
  from I/O behind small interfaces; prompt-injection isolation via
  `wrap_untrusted`; guaranteed termination via a finite research budget.
- **Agent modes**: normal, self-critiquing reflection (`--reflect`), and a
  multi-agent planner/researcher/writer team (`--multi-agent`).
- **Tools** (native function-calling): `search`, `read`, `calculate`, `now`,
  `get_weather`, `get_stock` (Yahoo Finance), `get_wikipedia`, `arxiv_search`,
  `convert` (units + currencies), `get_news` (Hacker News), `get_github`,
  `get_dictionary`, `crossref_search`, `read_pdf`, and `finish` — most needing
  no API key. Single-argument tools are declared once in a `tool_registry`.
- **Search**: DuckDuckGo (free, default) with automatic fallback through Tavily
  and a custom HTTP endpoint.
- **Efficiency**: persistent fetch cache, parallel prefetch after search
  (`--prefetch`), optional LLM response cache (`--cache-llm`), and smart
  retry/backoff honoring `Retry-After`.
- **Quality**: explainable source-credibility ranking (gov/edu/established vs.
  social), extensible via a reputation file (`--reputation-file`); recency
  steering for time-sensitive questions; deterministic evaluation metrics plus
  an optional LLM judge and a cross-mode benchmark (`research-agent-eval`).
- **Reports**: cited Markdown with style control (`--style brief|standard|deep`)
  and language control (`--lang`); direct export to PDF and DOCX with clickable
  source links; HTML export in the UI.
- **Long-term memory** across sessions (`--memory`).
- **CLI**: interactive follow-up chat (`--chat`) and a budget progress line with
  `-v`.
- **Web UI** (Streamlit): bilingual (Vietnamese/English), live agent steps,
  streaming report, source previews, follow-up chat, persistent history,
  side-by-side model comparison, and advanced toggles.
- **Packaging & ops**: `Dockerfile`, Streamlit Cloud config, PyPI publish
  workflow (Trusted Publishing), and CI on Python 3.11-3.13 enforcing lint,
  type-checks, and ≥80% test coverage.

[Unreleased]: https://github.com/tridpt/research-agent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tridpt/research-agent/releases/tag/v0.1.0
