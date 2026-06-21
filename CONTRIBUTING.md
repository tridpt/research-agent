# Contributing to research-agent

Thanks for your interest in improving research-agent! This guide covers the
conventions that keep the codebase consistent and reliable.

## Development setup

```powershell
uv sync --all-extras
```

`uv.lock` is committed so this matches CI exactly. If you do not use uv, run
`python -m pip install -e ".[dev,ui]"` instead.

## Before you commit

All four must pass (CI enforces them on Python 3.11–3.13):

```powershell
uv run ruff check src tests ui          # lint + import sorting
uv run python -m compileall -q src ui   # syntax check
uv run mypy src                         # static type checking
uv run pytest                           # tests (incl. property-based and UI smoke)
```

`uv run ruff check --fix src tests ui` auto-fixes most lint issues.

## Code conventions

- **Keep the deterministic core pure.** Loop control, budget enforcement,
  citation validation, parsing, etc. must be pure functions (no network, no
  clock, no file I/O). Push side effects to the boundary modules
  (`llm.py`, `search_tool.py`, `fetch_tool.py`, `cache.py`, `report_writer.py`).
- **All web content is untrusted data.** Never concatenate fetched content into
  system instructions; always route it through `wrap_untrusted`.
- **Every loop must terminate.** New stopping logic must respect the finite
  `ResearchBudget`.
- **Type hints everywhere.** `mypy` runs in CI.

## Tests

- Add **unit tests** for examples, boundaries, and error paths.
- Add a **property-based test** (hypothesis, ≥100 examples) when you introduce a
  new pure function with a universal invariant. Tag it:
  `# Feature: research-agent, Property N: <description>`.
- The UI has an offline startup smoke test in `tests/test_ui_smoke.py`. Update
  it when changing initial UI controls; still launch the app manually for
  interaction changes that need visual review.

## Adding a new agent tool

1. Add a schema to `TOOL_SCHEMAS` in `src/research_agent/tools.py`.
2. Add the action to `ActionType` (`models.py`) and handle it in
   `parse_decision` (`decision.py`).
3. Handle the action inside `run_session` (`agent.py`).
4. (Optional) localize the step label in `ui/app.py` (`render_step_vi`).
5. Add tests.

See [TAI_LIEU_KY_THUAT.md](TAI_LIEU_KY_THUAT.md) §14 for more extension points.

## Commit messages

Use short, imperative summaries, e.g.:

```
Add PDF-reading tool to the agent
Fix retry backoff to read Retry-After from error body
```

## Reporting issues

Include: the command/UI action you ran, the provider/model, and the full error
message (redact API keys).
