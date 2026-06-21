"""Pure Markdown rendering of a Report."""
from __future__ import annotations

from .models import Report
from .source_quality import is_local_pdf_source, source_display_name, source_quality_summary


def render_markdown(report: Report) -> str:
    """Render a Report as Markdown including a Sources section.

    Every fetched Source URL appears in the output (Property 6).
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
                f"{source_display_name(src.url)} (`{src.url}`)"
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
