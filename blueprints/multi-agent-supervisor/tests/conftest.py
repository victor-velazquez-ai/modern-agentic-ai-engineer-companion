"""Make the blueprint importable without an install.

Adds ``src/`` to ``sys.path`` so ``import multi_agent_supervisor`` works whether you
ran ``pip install -e .`` or just ``pytest`` from the blueprint root. Also forces
``COMPANION_MOCK=1`` for the whole session — tests must never spend money.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("COMPANION_MOCK", "1")

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
