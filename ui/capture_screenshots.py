"""Capture screenshots of the running Streamlit UI for the README.

Prereqs:
    pip install playwright && python -m playwright install chromium
    Streamlit app running at http://localhost:8501

Usage:
    python ui/capture_screenshots.py

It reads the API key/model from .env, fills the form, runs one research session,
and saves screenshots to docs/screenshots/.
"""
from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:8501"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1400})
        page.goto(URL, wait_until="networkidle", timeout=60000)
        time.sleep(3)

        # 1. Initial screen (config sidebar + question box).
        page.screenshot(path=str(OUT / "01-home.png"), full_page=True)
        print("saved 01-home.png")

        # 2. Type a question and start research.
        try:
            qbox = page.get_by_placeholder("Ví dụ: Sự khác nhau giữa SQL và NoSQL là gì?")
            qbox.fill("Docker là gì?")
            page.get_by_role("button", name="Bắt đầu nghiên cứu").click()
            # Let the agent run; capture the live steps.
            time.sleep(12)
            page.screenshot(path=str(OUT / "02-running.png"), full_page=True)
            print("saved 02-running.png")
            # Wait for completion (report + sources).
            time.sleep(25)
            page.screenshot(path=str(OUT / "03-report.png"), full_page=True)
            print("saved 03-report.png")
        except Exception as exc:  # noqa: BLE001
            print(f"interaction step skipped: {exc}")

        browser.close()


if __name__ == "__main__":
    main()
