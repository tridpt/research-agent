"""Direct PDF export of a report.

Turns a Markdown report into a real ``.pdf`` file. Markdown parsing into simple
typed blocks is a pure function (easy to test). The actual PDF rendering uses
``fpdf2`` (an optional dependency) with a Unicode TrueType font discovered on
the system, so Vietnamese and other non-Latin text render correctly.

If ``fpdf2`` or a Unicode font is unavailable, ``render_pdf_bytes`` raises
``PdfExportError`` and callers fall back to the HTML export.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Common locations of a broad-coverage Unicode TrueType font, by platform.
_FONT_CANDIDATES = (
    # Windows
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
    # Linux (DejaVu ships on most distros and on GitHub Actions runners)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    # macOS
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


class PdfExportError(RuntimeError):
    """Raised when a PDF cannot be produced (missing fpdf2 or Unicode font)."""


@dataclass(frozen=True)
class PdfBlock:
    """A simple typed line of content for layout.

    ``kind`` is one of: ``h1``, ``h2``, ``h3``, ``bullet``, ``para``. ``link`` is
    an optional URL that makes the whole block clickable (used for sources).
    """

    kind: str
    text: str
    link: str | None = None


_INLINE_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*|__([^_]+)__")
_ITALIC_RE = re.compile(r"\*([^*]+)\*|_([^_]+)_")
_CODE_RE = re.compile(r"`([^`]+)`")


def strip_inline_markdown(text: str) -> str:
    """Pure: remove inline Markdown emphasis/code/link syntax, keep readable text."""
    text = _INLINE_LINK_RE.sub(lambda m: m.group(1), text)
    text = _BOLD_RE.sub(lambda m: m.group(1) or m.group(2) or "", text)
    text = _ITALIC_RE.sub(lambda m: m.group(1) or m.group(2) or "", text)
    text = _CODE_RE.sub(lambda m: m.group(1), text)
    return text.strip()


_BARE_URL_RE = re.compile(r"https?://[^\s)\]]+")


def extract_link(text: str) -> str | None:
    """Pure: the first URL in a line (Markdown link target or bare URL), or None."""
    m = _INLINE_LINK_RE.search(text)
    if m:
        return m.group(2)
    m = _BARE_URL_RE.search(text)
    if m:
        return m.group(0).rstrip(".,")
    return None


def markdown_to_blocks(markdown: str) -> list[PdfBlock]:
    """Pure: parse Markdown into a flat list of typed layout blocks.

    Recognizes ATX headings (``#``..``###``), unordered/ordered list items, and
    paragraphs. Fenced code blocks are emitted as plain paragraphs. Blank lines
    are dropped (block separation is handled by the renderer).
    """
    blocks: list[PdfBlock] = []
    in_code = False
    for raw in (markdown or "").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if not stripped:
            continue
        if in_code:
            blocks.append(PdfBlock("para", line))
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if heading:
            level = len(heading.group(1))
            blocks.append(PdfBlock(f"h{level}", strip_inline_markdown(heading.group(2))))
            continue
        bullet = re.match(r"^[-*+]\s+(.*)$", stripped)
        if bullet:
            blocks.append(PdfBlock("bullet", strip_inline_markdown(bullet.group(1)), extract_link(bullet.group(1))))
            continue
        ordered = re.match(r"^(\d+)[.)]\s+(.*)$", stripped)
        if ordered:
            blocks.append(PdfBlock(
                "bullet",
                f"{ordered.group(1)}. {strip_inline_markdown(ordered.group(2))}",
                extract_link(ordered.group(2)),
            ))
            continue
        blocks.append(PdfBlock("para", strip_inline_markdown(stripped), extract_link(stripped)))
    return blocks


def find_unicode_font(candidates: tuple[str, ...] = _FONT_CANDIDATES) -> str | None:
    """Return the path of the first available Unicode TTF, or None."""
    for path in candidates:
        if Path(path).is_file():
            return path
    return None


_BLOCK_STYLE = {
    "h1": (18, 8, 4),
    "h2": (15, 7, 3),
    "h3": (13, 6, 2),
    "para": (11, 2, 2),
    "bullet": (11, 1, 1),
}


def render_pdf_bytes(
    title: str,
    markdown: str,
    *,
    font_path: str | None = None,
) -> bytes:
    """Render a Markdown report to PDF bytes.

    Raises PdfExportError if ``fpdf2`` is not installed or no Unicode font can
    be located (so the caller can fall back to HTML export).
    """
    try:
        from fpdf import FPDF
    except ImportError as exc:  # pragma: no cover - exercised only without fpdf2
        raise PdfExportError(
            "PDF export needs the optional 'fpdf2' package. Install with: "
            "pip install \"research-agent[pdf]\"."
        ) from exc

    resolved_font = font_path or find_unicode_font()
    if not resolved_font:
        raise PdfExportError(
            "No Unicode TrueType font found for PDF export. Use the HTML export "
            "instead, or set a font path explicitly."
        )

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.add_font("body", "", resolved_font)
    pdf.set_font("body", size=20)
    pdf.multi_cell(0, 10, (title or "Research Report").strip())
    pdf.ln(2)

    for block in markdown_to_blocks(markdown):
        size, space_before, space_after = _BLOCK_STYLE.get(block.kind, (11, 2, 2))
        if space_before:
            pdf.ln(space_before)
        pdf.set_font("body", size=size)
        text = f"  •  {block.text}" if block.kind == "bullet" else block.text
        pdf.multi_cell(0, size * 0.55 + 2, text, link=block.link or "")
        if space_after:
            pdf.ln(space_after)

    output = pdf.output()
    return bytes(output)


def write_pdf(title: str, markdown: str, path: Path, *, font_path: str | None = None) -> Path:
    """Render and write a PDF report to ``path``; return the written path."""
    data = render_pdf_bytes(title, markdown, font_path=font_path)
    path = Path(path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path
