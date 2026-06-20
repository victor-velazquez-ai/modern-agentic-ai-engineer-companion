"""Make ``src/agent_loop`` importable in tests without an install step.

A reader should be able to ``pytest tests/`` straight from a clone, before ``pip install -e .``.
We put ``src/`` on ``sys.path`` here so the package imports either way. (In CI the package is
installed and this is a harmless no-op.)
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
