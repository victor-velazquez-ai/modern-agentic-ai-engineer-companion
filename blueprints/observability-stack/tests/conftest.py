"""Make ``src/`` importable so the tests run without an install step.

A real CI run would `pip install -e .` first; for a read-it-by-running-it blueprint we keep
``pytest tests/`` working straight from a clone by prepending the package's ``src`` dir to
``sys.path``. Nothing here touches the network or needs a key.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
