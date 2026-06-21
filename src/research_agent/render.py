"""Pure Markdown rendering of a Report."""
from __future__ import annotations

import re

from .models import Report
from .source_quality import is_local_pdf_source, source_display_name, source_quality_summary


def render_markdown(report: Report) -> str:
    """Render a Report as Markdown including a Sources section.

    External sources retain their URLs. Local PDFs use safe user-facing metadata
    instead of their internal identifier.
    """
    lines: list[str] = []
    lines.append(f"# Research Report: {report.question}")
    lines.append("")
    lines.append(report.body_markdown.strip())
    lines.append("")
    lines.append("## Sources")
    lines.append("")
    if report.sources:
        for i, src in enumerate(report.sources, start=1):
            quality = source_quality_summary(src)
            label = (
                _local_pdf_label(src.content, src.url)
                if is_local_pdf_source(src.url)
                else f"[{src.url}]({src.url})"
            )
            lines.append(
                f"{i}. {label} — "
                f"Quality: {quality.label} ({quality.score}/100; {quality.reason})"
            )
    else:
        lines.append("_No sources were collected._")
    lines.append("")
    return "\n".join(lines)


def _local_pdf_label(content: str, url: str) -> str:
    """Build safe PDF provenance without exposing a temporary local path."""
    label = source_display_name(url)
    match = re.search(r"^Pages: (\d+)$", content, flags=re.MULTILINE)
    if match is None:
        return label
    count = int(match.group(1))
    page_label = "page" if count == 1 else "pages"
    return f"{label} ({count} {page_label})"
