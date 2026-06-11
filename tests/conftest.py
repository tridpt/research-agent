"""Shared pytest/hypothesis configuration.

Registers a hypothesis profile that runs at least 100 examples per property
test, as required by the design's Testing Strategy.
"""
from __future__ import annotations

import sys
from pathlib import Path

from hypothesis import HealthCheck, settings

# Ensure the src/ layout package is importable during tests without an install.
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

settings.register_profile(
    "default",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("default")
