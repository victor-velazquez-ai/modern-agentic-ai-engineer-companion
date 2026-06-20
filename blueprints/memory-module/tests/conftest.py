"""Make ``src/`` importable so ``pytest`` runs without installing the package.

A blueprint must be runnable straight from a clone (study-and-adapt, not pip-install-first), so we
add the local ``src/`` directory to ``sys.path``. In a real deployment you would ``pip install -e
.`` and drop this shim.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
