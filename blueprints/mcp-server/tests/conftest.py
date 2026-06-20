"""Make ``src/`` importable when the package isn't pip-installed.

Lets ``pytest tests/`` and ``python demo.py`` run straight from a clone with no install step —
the offline, zero-setup promise of the blueprint.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
