"""Pure citation integrity enforcement."""
from __future__ import annotations

from .models import Report, Source


def validate_citations(report: Report, sources: list[Source]) -> Report:
    """Return a copy of ``report`` whose citations only reference fetched URLs.

    Any citation whose URL is not among the actually-fetched sources is
    dropped, so the final report can never cite a source that was never read.
    """
    valid_urls = {s.url for s in sources}
    kept = tuple(c for c in report.citations if c.url in valid_urls)
    if kept == report.citations:
        return report
    return Report(
        question=report.question,
        body_markdown=report.body_markdown,
        citations=kept,
        sources=report.sources,
        no_information=report.no_information,
    )
