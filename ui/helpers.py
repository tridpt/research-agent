"""Helper utilities for the Streamlit UI: persistent history and HTML export."""
from __future__ import annotations

import html
import json
import time
from pathlib import Path
from typing import Any

import bleach
import markdown as markdown_lib

HISTORY_PATH = Path(__file__).resolve().parent.parent / ".research_agent_history.json"
MAX_HISTORY = 50
_ALLOWED_HTML_TAGS = {
    "a", "blockquote", "br", "code", "em", "h1", "h2", "h3", "h4", "hr",
    "li", "ol", "p", "pre", "strong", "table", "tbody", "td", "th", "thead", "tr", "ul",
}
_ALLOWED_HTML_ATTRIBUTES = {"a": ["href", "title"]}


def load_history() -> list[dict[str, Any]]:
    """Load saved research history from disk (newest first)."""
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_history(history: list[dict[str, Any]]) -> None:
    """Persist history to disk (best-effort, capped to MAX_HISTORY items)."""
    try:
        HISTORY_PATH.write_text(
            json.dumps(history[:MAX_HISTORY], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def add_history_item(
    history: list[dict[str, Any]],
    *,
    question: str,
    markdown: str,
    sources: list[dict[str, str]],
    elapsed: float,
    mode: str,
    usage: str = "",
) -> list[dict[str, Any]]:
    """Prepend a new item, persist, and return the updated history list."""
    item = {
        "question": question,
        "markdown": markdown,
        "sources": sources,
        "elapsed": round(elapsed, 1),
        "mode": mode,
        "usage": usage,
        "when": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    history.insert(0, item)
    del history[MAX_HISTORY:]
    save_history(history)
    return history


def report_to_html(question: str, markdown: str) -> str:
    """Wrap a Markdown report in a self-contained, printable HTML page.

    Markdown is rendered and sanitized before it reaches the HTML document, so
    model-generated raw HTML and unsafe URL schemes cannot execute on open.
    """
    rendered = markdown_lib.markdown(markdown, extensions=["fenced_code", "tables"])
    safe_body = bleach.clean(
        rendered,
        tags=_ALLOWED_HTML_TAGS,
        attributes=_ALLOWED_HTML_ATTRIBUTES,
        protocols={"http", "https"},
        strip=True,
        strip_comments=True,
    )
    safe_title = html.escape(question)
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>
  body {{ max-width: 820px; margin: 40px auto; padding: 0 20px;
         font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
         line-height: 1.6; color: #222; }}
  h1, h2, h3 {{ line-height: 1.25; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  th {{ background: #f5f5f5; }}
  code {{ background: #f3f3f3; padding: 2px 5px; border-radius: 4px; }}
  pre {{ background: #f3f3f3; padding: 12px; border-radius: 8px; overflow-x: auto; }}
  a {{ color: #1a6fdb; word-break: break-all; }}
  blockquote {{ border-left: 4px solid #ddd; margin: 0; padding-left: 16px; color: #555; }}
  @media print {{ body {{ margin: 0; }} }}
</style>
</head>
<body>
<div id="content">{safe_body}</div>
</body>
</html>"""


def parse_model_list(text: str, max_models: int = 4) -> list[str]:
    """Parse a comma/newline-separated list of model names into a unique list.

    Order is preserved, blanks and duplicates are removed, and the result is
    capped at ``max_models`` so a side-by-side comparison stays manageable.
    """
    seen: set[str] = set()
    models: list[str] = []
    for raw in (text or "").replace("\n", ",").split(","):
        name = raw.strip()
        if name and name not in seen:
            seen.add(name)
            models.append(name)
        if len(models) >= max_models:
            break
    return models
