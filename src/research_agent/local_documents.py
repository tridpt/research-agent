"""Safety boundary for user-approved local documents."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

MAX_APPROVED_PDF_BYTES = 20 * 1024 * 1024


def approved_pdf_path(
    requested_path: str,
    allowed_paths: Sequence[Path],
    max_bytes: int = MAX_APPROVED_PDF_BYTES,
) -> tuple[Path | None, str | None]:
    """Return a canonical approved PDF path, or a user-safe rejection reason."""
    if not requested_path:
        return None, "no PDF was selected by the user"
    try:
        candidate = Path(requested_path).expanduser().resolve(strict=True)
    except OSError:
        return None, "selected PDF does not exist"

    approved: set[Path] = set()
    for path in allowed_paths:
        try:
            approved.add(Path(path).expanduser().resolve(strict=True))
        except OSError:
            continue
    if candidate not in approved:
        return None, "PDF path was not explicitly approved by the user"
    if candidate.suffix.lower() != ".pdf" or not candidate.is_file():
        return None, "approved document is not a PDF file"
    try:
        if candidate.stat().st_size > max_bytes:
            return None, f"PDF exceeds the {max_bytes // (1024 * 1024)} MB limit"
    except OSError:
        return None, "could not inspect approved PDF"
    return candidate, None
