"""Record an animated GIF of a live research run for the README.

Prereqs:
    pip install playwright pillow && python -m playwright install chromium
    Streamlit app running at http://localhost:8501 (with a working key in .env)

Usage:
    python ui/capture_gif.py
"""
from __future__ import annotations

import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
FRAMES = OUT / "frames"
FRAMES.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:8501"

N_FRAMES = 24
INTERVAL = 1.5  # seconds between frames


def main() -> None:
    frame_paths: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 760})
        page.goto(URL, wait_until="networkidle", timeout=60000)
        time.sleep(3)

        page.get_by_placeholder("Ví dụ: Sự khác nhau giữa SQL và NoSQL là gì?").fill(
            "Lợi ích của việc đọc sách là gì?"
        )
        page.get_by_role("button", name="Bắt đầu nghiên cứu").click()

        for i in range(N_FRAMES):
            fp = FRAMES / f"f{i:02d}.png"
            page.screenshot(path=str(fp))
            frame_paths.append(fp)
            print(f"frame {i+1}/{N_FRAMES}")
            time.sleep(INTERVAL)

        browser.close()

    # Assemble GIF (downscale for a smaller file).
    imgs = [Image.open(fp).convert("RGB") for fp in frame_paths]
    w, h = imgs[0].size
    scale = 800 / w
    imgs = [im.resize((800, int(h * scale))) for im in imgs]
    gif_path = OUT / "demo.gif"
    imgs[0].save(
        gif_path,
        save_all=True,
        append_images=imgs[1:],
        duration=900,
        loop=0,
        optimize=True,
    )
    print(f"saved {gif_path} ({gif_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
