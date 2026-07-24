# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- **Web UI credential handling hardened**: server-managed API keys are never
  pre-filled into a browser widget and their base URL is locked; personal LLM
  and Tavily keys are kept only in the current Streamlit session and are no
  longer written to `.env`. Adds an explicit "server managed" vs "personal API
  key" mode.
- **Custom LLM endpoints restricted in the web UI**: a custom base URL must use
  HTTPS, carry no embedded credentials/query/fragment, and resolve to a host in
  the built-in allowlist (Groq/Gemini/OpenAI) or the maintainer-configured
  `RESEARCH_AGENT_ALLOWED_LLM_HOSTS`.
- **Fetch response size cap**: sources are streamed and rejected once they
  exceed a 5 MiB limit, preventing memory exhaustion from oversized responses.
- **DNS-rebinding defense**: the fetch tool verifies the *actual* connected peer
  IP (not just the pre-request DNS answer) and rejects private/loopback/reserved
  addresses, closing a TOCTOU gap in the SSRF check.
- **Robust LLM response handling**: malformed JSON or an invalid
  OpenAI-compatible schema now raises `LLMError` instead of leaking
  `JSONDecodeError`/`KeyError`/`IndexError` and crashing a session.
- **Dependency updates**: bumped `pypdf` (6.14.2), `Pillow` (12.3.0), and
  `GitPython` (3.1.55) to patched releases.
- **Supply-chain automation**: added a `pip-audit` CI job that fails on known
  vulnerabilities and a Dependabot config for weekly `uv` and GitHub Actions
  updates.
- **Hardened Docker image**: multi-stage build running as a non-root user, with
  only runtime dependencies (no dev/test toolchain), a health check, and the
  console script on `PATH`.

### Changed

- **`max_seconds` is now a hard deadline for LLM retries**: retry backoff never
  waits past the remaining budget, and per-request LLM/fetch timeouts are capped
  by `max_seconds` (never below a 1s floor).
- **Web UI refactored for testability**: the credential/endpoint policy moved to
  the pure module `ui/config_ui.py` and the trace-step renderer to `ui/steps.py`,
  each covered by unit tests.

### Added

- **Visual theme** (`ui/theme.py`): a gradient hero banner, styled primary
  buttons, pill-style tabs, and rounded source cards, with dark-mode contrast
  fixes.

## [0.1.3] - 2026-07-09

### Changed

- **Web UI reorganized into tabs**: the report, model comparison, and research
  history now live in three dedicated tabs (📄 Báo cáo / ⚖️ So sánh / 🕘 Lịch sử)
  below a persistent question + run bar, replacing the single long scrolling
  page. Model comparison is promoted from a collapsed expander to its own tab.

### Added

- **PubMed tool** (`pubmed_search`): the agent can now search PubMed for
  peer-reviewed biomedical/clinical literature (title, authors, journal, year,
  PMID) via NCBI's public E-utilities (no API key), complementing the arXiv and
  CrossRef tools for medical, health, and life-sciences questions. Shown in the
  web UI's live step log (🧬).
- **OpenAlex tool** (`openalex_search`): search OpenAlex, a large open index of
  scholarly works across all disciplines (title, authors, venue, year, DOI),
  via its public REST API (no API key) — a broad general-purpose academic
  search when arXiv/PubMed/CrossRef are too narrow. Shown in the web UI's live
  step log (🎓).

## [0.1.2] - 2026-07-03

### Fixed

- Synced `research_agent.__version__` and the `uv.lock` entry to the released
  package version so `import research_agent` and `uv lock --check` (CI) agree
  with `pyproject.toml`.

## [0.1.1] - 2026-07-03

### Added

- **Per-domain reputation weights**: a reputation file may now include a
  `weights` map (e.g. `{"my-lab.example": 15, "spam.example": -30}`) that nudges
  a domain's source-quality score up or down on top of the category heuristics,
  matching a host or any of its subdomains (`--reputation-file`).
- **Reputation in the web UI**: the sidebar has a Source-reputation field to
  paste the same JSON (established/low_evidence/weights), applied for the run.
- **Streamlit Cloud secrets**: the web UI now reads its default provider
  configuration (API key, base URL, model) from `st.secrets` when deployed on
  Streamlit Community Cloud, enabling a one-click hosted demo. Precedence is
  secrets > environment > saved `.env`.

### Tests

- Raised total coverage from 83% to 93% with focused tests for the CLI wiring,
  the OpenAI-compatible LLM client (HTTP/retry/recovery/streaming paths), the
  search providers and fallback, the HTTP fetch tool (redirects, blocking, SSRF
  guards), and the evaluation `main`/runner wiring.

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

[Unreleased]: https://github.com/tridpt/research-agent/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/tridpt/research-agent/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/tridpt/research-agent/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/tridpt/research-agent/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/tridpt/research-agent/releases/tag/v0.1.0
