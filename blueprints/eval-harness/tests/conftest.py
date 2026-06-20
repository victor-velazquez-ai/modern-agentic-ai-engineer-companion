"""Test config — put the blueprint's ``src/`` on the import path.

Lets ``pytest tests/`` run from the blueprint folder without an editable install, matching
the README's quick-start. (A real consumer would ``pip install -e .`` instead.)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test runs offline: no test may spend tokens."""

    monkeypatch.setenv("COMPANION_MOCK", "1")


@pytest.fixture()
def dataset_path() -> Path:
    return Path(__file__).resolve().parents[1] / "datasets" / "example.jsonl"
