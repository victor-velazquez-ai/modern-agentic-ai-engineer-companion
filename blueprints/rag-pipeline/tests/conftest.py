"""Test bootstrap: make ``rag_pipeline`` importable from ``src/`` without installation.

The blueprint is "study & adapt" reference code, not an installed wheel, so tests put the
package's ``src/`` on ``sys.path`` directly. Everything runs in the default MOCK mode (no key,
no network), which we pin explicitly so a developer's real env can't leak in and make a test
non-deterministic.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Force deterministic, offline behavior for the whole test session.
os.environ.setdefault("COMPANION_MOCK", "1")
