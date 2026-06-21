"""Composition seam — make the sibling *pattern* blueprints importable without forking them.

A solution blueprint's whole point is that it **reuses** the pattern blueprints rather than
copying them. Each pattern lives in a sibling folder with its code under ``<pattern>/src/``, so
to ``import agent_loop`` (etc.) we add those ``src/`` directories to ``sys.path`` once, here, at
import time. Nothing is vendored; edit a pattern blueprint and this solution picks up the change.

This mirrors how the pattern blueprints' own ``demo.py`` files bootstrap their package
(``sys.path.insert(0, .../src)``) — we just do it for several siblings at once.

Layout assumed (the repo's blueprint convention)::

    blueprints/
      agent-loop/src/agent_loop/...
      rag-pipeline/src/rag_pipeline/...
      mcp-server/src/mcp_server/...
      eval-harness/src/eval_harness/...
      observability-stack/src/observability_stack/...
      sales-revops-automation/         <- this package lives here
        revops/compose.py

If a pattern's ``src/`` is missing (e.g. someone is reading just this folder), we skip it
silently; the importing module will then raise a clear ``ModuleNotFoundError`` naming the
pattern, which is the right signal.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The five pattern blueprints this solution composes (PLAN -> "Composes").
PATTERN_BLUEPRINTS: tuple[str, ...] = (
    "agent-loop",
    "rag-pipeline",
    "mcp-server",
    "eval-harness",
    "observability-stack",
)

# blueprints/sales-revops-automation/revops/compose.py -> parents[2] == blueprints/
_BLUEPRINTS_DIR = Path(__file__).resolve().parents[2]


def blueprints_root() -> Path:
    """The directory holding all blueprint folders (``.../blueprints``)."""
    return _BLUEPRINTS_DIR


def ensure_on_path() -> list[str]:
    """Add each pattern blueprint's ``src/`` to ``sys.path`` (idempotent).

    Returns the list of paths that are now importable, so a caller (or a smoke test) can assert
    the composition is wired. Safe to call repeatedly — already-present paths are left alone.
    """
    added: list[str] = []
    for slug in PATTERN_BLUEPRINTS:
        src = _BLUEPRINTS_DIR / slug / "src"
        if src.is_dir():
            s = str(src)
            if s not in sys.path:
                sys.path.insert(0, s)
            added.append(s)
    return added


# Wire the path the moment this module is imported, so ``from revops.compose import ...`` is all
# the rest of the package needs before importing the pattern packages.
ensure_on_path()


def data_dir() -> Path:
    """Absolute path to this solution blueprint's bundled sample ``data/`` directory."""
    return Path(__file__).resolve().parents[1] / "data"
