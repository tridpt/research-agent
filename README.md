# research-agent 🔎🤖

![CI](https://github.com/tridpt/research-agent/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)

**What is it?** An autonomous AI research agent. You ask a question; it searches
the web over multiple rounds, reads sources, decides on its own when it has
enough, and writes a **cited Markdown report** — so you can trust and verify it.

**Who is it for?** Anyone who needs to research a topic quickly (students,
developers, writers), and anyone learning **how AI agents actually work** under
the hood.

**What problem does it solve?** It turns "spend an hour reading 10 tabs" into
"ask once, get a grounded, cited summary" — while staying transparent about every
step it takes.

Runs from the **command line** or a **web UI** (Streamlit). Works with any
OpenAI-compatible LLM (Groq, Gemini, OpenAI, local Ollama).

## 📚 Documentation

| File | What it covers |
|---|---|
| [README.md](README.md) | This file — overview, install, usage (English) |
| [HUONG_DAN.md](HUONG_DAN.md) | Hướng dẫn sử dụng chi tiết cho người dùng (Tiếng Việt) |
| [TAI_LIEU_KY_THUAT.md](TAI_LIEU_KY_THUAT.md) | Tài liệu kỹ thuật: kiến trúc, module, luồng dữ liệu (Tiếng Việt) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute (conventions, tests) |

## 📸 Screenshots

The web UI (Streamlit) — configure a provider, ask a question, watch the agent's
steps in Vietnamese, and read the cited report:

![Demo](docs/screenshots/demo.gif)

| Home | Researching (live steps) | Cited report |
|---|---|---|
| ![Home](docs/screenshots/01-home.png) | ![Running](docs/screenshots/02-running.png) | ![Report](docs/screenshots/03-report.png) |

> The CLI offers the same capabilities (`research-agent "your question" -v`).

## How it works

```
question ─▶ Agent_Loop ─▶ decide: SEARCH / READ / FINISH
                │            │
                │            ├─ Search_Tool (web search)
                │            └─ Fetch_Tool  (download + extract text)
                ▼
          Synthesizer ─▶ cited Markdown Report ─▶ file + console summary
```

Key design idea: the **deterministic core** (loop control, budget enforcement,
citation validation, content truncation, domain filtering) is made of pure
functions, while the **unpredictable I/O** (LLM, search, fetch, file writes)
lives behind small interfaces. That makes the agent easy to read, test, and
reason about.

### Safety properties
- All web content is treated as **data, never instructions** (prompt-injection
  resistant via `wrap_untrusted`).
- The agent **always terminates** thanks to a finite research budget
  (max rounds / sources / seconds).
- Citations can only point to sources that were actually fetched.
- Web reads are restricted to search results and public HTTP(S) destinations;
  private, loopback, and link-local networks are blocked, including redirects.
- Local PDFs are opt-in: the agent can only read a file explicitly selected for
  the current run with `--pdf` (or the UI file picker). An approved PDF is
  listed as a user-provided source by filename and page count; temporary local
  paths are never included in the report.

### Efficiency & quality
- **Persistent fetch cache**: a URL read once is reused from disk across
  sessions (disable with `--no-cache`, configure with `--cache-dir`).
- **Source diversity**: encourages at least `--min-domains` distinct domains and
  never collects more than `--max-per-domain` pages from one site. If the model
  tries to finish too early, the agent auto-reads one more new-domain source.
- **Source-quality signals**: ranks official/academic domains above social or
  user-generated platforms, then labels each fetched source using its domain
  type and the amount of extractable evidence. These labels are transparent
  heuristics, not fact-checks.
- **Smart retry/backoff**: honors a provider `Retry-After` header on 429/503,
  otherwise uses capped exponential backoff.

### Agent tools
The agent chooses among these tools on each step via native function-calling:
- **search** — run a web search.
- **read** — fetch and read a source URL.
- **calculate** — evaluate a safe arithmetic expression (no `eval`; AST-based,
  allow-listed operators) for precise numbers in the report.
- **now** — get the current date/time (for "latest"/"today"/recency questions).
- **get_weather** — retrieve current weather from wttr.in.
- **read_pdf** — read a PDF explicitly selected by the user for the current run.
- **finish** — stop and synthesize the cited report.

### Agent modes
- **Native tool-calling**: the model selects actions via real function-calling
  (not JSON-mode prompting), which is more reliable. The provider also recovers
  gracefully when open models emit a tool call as plain text (a known quirk of
  some Llama/OSS models on Groq).
- **Reflection** (`--reflect`): after drafting, the agent critiques its own
  report, scores it, and re-researches the gaps until it's good enough or hits
  `--reflect-iterations`.
- **Multi-agent** (`--multi-agent`): a planner splits the question into
  sub-questions, a researcher gathers sources for each, and a writer synthesizes
  one cited report.

> Tip: on providers with a low tokens-per-minute limit (e.g. Groq free tier),
> lower `RESEARCH_AGENT_PER_SOURCE_CHARS` (e.g. 1500-2500) and `--max-sources`
> so each request stays under the limit.

## Install

```powershell
python -m pip install -e ".[dev]"
```

To permit one local PDF in a CLI run, opt in explicitly:

```powershell
research-agent "Summarize this document" --pdf C:\Documents\report.pdf
```

## Configure

Set your LLM provider credentials via environment variables. The agent works
with any OpenAI-compatible API. Recommended free options:

**Groq** (fast, generous free tier, recommended for live use):
```powershell
$env:RESEARCH_AGENT_API_KEY  = "gsk_...(your Groq key)"
$env:RESEARCH_AGENT_BASE_URL = "https://api.groq.com/openai/v1"
$env:RESEARCH_AGENT_MODEL    = "openai/gpt-oss-20b"
```

**Gemini** (via its OpenAI-compatible endpoint; small free tier):
```powershell
$env:RESEARCH_AGENT_API_KEY  = "AIza...(your Gemini key)"
$env:RESEARCH_AGENT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
$env:RESEARCH_AGENT_MODEL    = "gemini-2.5-flash-lite"
```

| Variable | Required | Default |
|---|---|---|
| `RESEARCH_AGENT_API_KEY` | ✅ | — |
| `RESEARCH_AGENT_BASE_URL` | | `https://api.openai.com/v1` |
| `RESEARCH_AGENT_MODEL` | | `gpt-4o-mini` |
| `RESEARCH_AGENT_SEARCH_API_KEY` | | — |
| `RESEARCH_AGENT_SEARCH_ENDPOINT` | | — (defaults to free DuckDuckGo search) |
| `RESEARCH_AGENT_BLOCKED_DOMAINS` | | (none) |
| `RESEARCH_AGENT_MAX_ROUNDS` / `..._SOURCES` / `..._SECONDS` | | `8` / `12` / `180` |

## Run

```powershell
research-agent "What are the tradeoffs of RAG vs fine-tuning?" -o report.md -v
```

Web search uses **DuckDuckGo by default** (no API key needed). To use a custom
search API instead, set `RESEARCH_AGENT_SEARCH_ENDPOINT` (and optionally
`RESEARCH_AGENT_SEARCH_API_KEY`).

Flags: `-o/--out`, `-v/--verbose`, `--max-rounds`, `--max-sources`,
`--max-seconds`, `--min-domains`, `--max-per-domain`, `--cache-dir`,
`--no-cache`, `--reflect`, `--reflect-iterations`, `--multi-agent`,
`--model`, `--provider`.

### Web UI

A simple Streamlit web interface is included:

```powershell
python -m pip install streamlit
streamlit run ui/app.py          # or: .\run-ui.ps1
```

Then open http://localhost:8501. Pick a provider, paste your API key, choose a
mode (normal / reflect / multi-agent), enter a question, and watch the agent's
steps live before the cited report appears.

> **Live demo:** there is no static demo link because this is a Python app
> (not a static site), so it can't run on GitHub Pages. To share it online, deploy
> to [Streamlit Community Cloud](https://streamlit.io/cloud) (users still supply
> their own API key). Locally it runs in any modern browser (Chrome, Edge,
> Firefox, Safari).

Examples:

```powershell
# Self-critiquing run (researches gaps until the draft is solid):
research-agent "Compare gRPC and REST for microservices" --reflect -v

# Multi-agent run (planner splits the question, researchers gather, writer synthesizes):
research-agent "State of solid-state batteries in 2026" --multi-agent -v
```

## Test

```powershell
python -m pytest
```

Property-based tests (hypothesis) validate the 10 correctness properties; unit
and integration tests cover examples, boundaries, and the end-to-end flow.

## Develop

```powershell
ruff check src tests     # lint
mypy src                 # type-check
pytest                   # tests
```

CI runs all three on Python 3.11-3.13 via GitHub Actions (`.github/workflows/ci.yml`).

## Build & distribute

```powershell
python -m build          # produces dist/*.whl and *.tar.gz
pip install dist/research_agent-0.1.0-py3-none-any.whl
```

## Search providers

The agent tries providers in order and **falls back automatically** when one
errors or returns nothing:

1. **Tavily** - set `RESEARCH_AGENT_TAVILY_API_KEY` (AI-oriented results).
2. **Custom HTTP API** - set `RESEARCH_AGENT_SEARCH_ENDPOINT`.
3. **DuckDuckGo** - free, no key; always available as the final fallback.

## Project layout

```
src/research_agent/
├── models.py         # immutable data models
├── config.py         # resolve_settings (pure)
├── cli.py            # argument parsing + main() wiring
├── content.py        # truncate / is_blocked / wrap_untrusted (pure)
├── search_tool.py    # web search behind SearchTool (incl. DuckDuckGo)
├── fetch_tool.py     # download + extract behind FetchTool
├── cache.py          # persistent URL fetch cache + CachingFetchTool
├── llm.py            # LLMProvider protocol + OpenAI-compatible client
├── decision.py       # parse_decision (pure)
├── retry.py          # retry policy (pure counting) + RetryingLLMProvider
├── agent.py          # decide_transition + build_messages (pure) + run_session
├── citations.py      # validate_citations (pure)
├── render.py         # render_markdown (pure)
├── synthesizer.py    # synthesize report
├── reflection.py     # self-critique loop (--reflect)
├── multi_agent.py    # planner/researcher/writer team (--multi-agent)
├── tools.py          # native function-calling tool schemas
├── observability.py  # render_trace (pure) + TraceEmitter
└── report_writer.py  # write_report
```

## Roadmap

Ideas for future versions (contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md)):

- [ ] More agent tools (e.g. stock data)
- [ ] Source-credibility ranking (prefer gov/edu/established domains)
- [ ] Long-term memory across sessions (reference past research)
- [ ] Direct PDF export (currently via HTML → print)
- [ ] Side-by-side model comparison in the web UI
- [ ] Streamlit Community Cloud deployment for a one-click live demo
- [ ] Automated quality evaluation across modes (built on `evaluate.py`)

## License

[MIT](LICENSE)
