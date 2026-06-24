"""Direct DOCX (Microsoft Word) export of a report.

Reuses the pure Markdown block parser from ``pdf_export`` and renders the blocks
into a ``.docx`` using ``python-docx`` (an optional dependency). Word handles
Unicode natively, so Vietnamese and other non-Latin text render correctly.

If ``python-docx`` is unavailable, ``render_docx_bytes`` raises
``DocxExportError`` and callers fall back to another export format.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from .pdf_export import markdown_to_blocks


class DocxExportError(RuntimeError):
    """Raised when a DOCX cannot be produced (missing python-docx)."""


_HEADING_LEVEL = {"h1": 1, "h2": 2, "h3": 3}


def render_docx_bytes(title: str, markdown: str) -> bytes:
    """Render a Markdown report to DOCX bytes.

    Raises DocxExportError if ``python-docx`` is not installed, so the caller
    can fall back to another export format.
    """
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover - exercised only without python-docx
        raise DocxExportError(
            "DOCX export needs the optional 'python-docx' package. Install with: "
            "pip install \"research-agent[docx]\"."
        ) from exc

    document = Document()
    document.add_heading((title or "Research Report").strip(), level=0)

    for block in markdown_to_blocks(markdown):
        level = _HEADING_LEVEL.get(block.kind)
        if level is not None:
            document.add_heading(block.text, level=level)
        elif block.kind == "bullet":
            document.add_paragraph(block.text, style="List Bullet")
        else:
            document.add_paragraph(block.text)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def write_docx(title: str, markdown: str, path: Path) -> Path:
    """Render and write a DOCX report to ``path``; return the written path."""
    data = render_docx_bytes(title, markdown)
    path = Path(path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path
