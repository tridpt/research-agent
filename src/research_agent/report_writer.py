"""ReportWriter: persist the Markdown report to disk."""
from __future__ import annotations

from pathlib import Path

from .errors import ReportWriteError


def write_report(markdown: str, path: Path) -> Path:
    """Write ``markdown`` to ``path``; return the written path.

    Raises ReportWriteError on any filesystem failure (no disk space, missing
    permissions, etc.) so the caller never treats the session as complete.
    """
    try:
        path = Path(path)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        return path
    except OSError as exc:
        raise ReportWriteError(f"Failed to write report to {path}: {exc}") from exc
