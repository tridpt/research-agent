"""Offline smoke coverage for the Streamlit application shell."""
from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "ui" / "app.py"


def test_ui_initial_render_has_no_exception_and_exposes_pdf_picker() -> None:
    """Catch startup/import regressions without needing an API key or network."""
    app = AppTest.from_file(str(APP_PATH))
    app.run(timeout=10)

    assert len(app.exception) == 0
    assert len(app.title) == 1
    assert len(app.file_uploader) == 1
