"""Composition seam: put the sibling **pattern blueprints** on the import path.

A solution blueprint *composes* the pattern blueprints — it must **not fork** them. There is
no install step in this teaching repo, so instead of copying code we add each sibling's
``src/`` directory to ``sys.path`` and import the real package. Edit a pattern blueprint and
this solution picks the change up; that is the whole point.

Directory layout (relative to this file)::

    blueprints/
      multi-agent-supervisor/src/   ← imported as `multi_agent_supervisor`
      rag-pipeline/src/             ← imported as `rag_pipeline`
      agent-loop/src/               ← imported as `agent_loop`
      eval-harness/src/             ← imported as `eval_harness`
      observability-stack/src/      ← imported as `observability_stack`
      research-due-diligence-agent/ ← (this solution)
        app/_compose.py             ← you are here

Call :func:`ensure_siblings_importable` once, early, before importing any sibling package.
:func:`demo.py`, :mod:`app.pipeline`, and the eval set all funnel through it, so the wiring
lives in exactly one place.
"""

from __future__ import annotations

import sys
from pathlib import Path

# blueprints/research-due-diligence-agent/app/_compose.py
#   parents[0] = app/
#   parents[1] = research-due-diligence-agent/
#   parents[2] = blueprints/            ← the shared root that holds every sibling
_BLUEPRINTS_ROOT = Path(__file__).resolve().parents[2]

# The pattern blueprints this solution composes, in dependency order. Each entry is the
# sibling folder name; its importable package lives under ``<folder>/src``.
SIBLING_BLUEPRINTS: tuple[str, ...] = (
    "multi-agent-supervisor",
    "rag-pipeline",
    "agent-loop",
    "eval-harness",
    "observability-stack",
)


def sibling_src(folder: str) -> Path:
    """Return the ``src/`` directory of a sibling pattern blueprint."""
    return _BLUEPRINTS_ROOT / folder / "src"


def ensure_siblings_importable() -> list[str]:
    """Prepend each present sibling's ``src/`` to ``sys.path`` (idempotent).

    Returns the list of folders that were found, so a caller can warn if a dependency is
    missing rather than failing with a bare ``ImportError`` later. Missing siblings are
    skipped silently here; the import that needs them will raise a clear error on use.
    """
    found: list[str] = []
    for folder in SIBLING_BLUEPRINTS:
        src = sibling_src(folder)
        if src.is_dir():
            found.append(folder)
            path = str(src)
            if path not in sys.path:
                sys.path.insert(0, path)
    return found


# Wire the path at import time so ``from app import ...`` Just Works without each module
# repeating the dance. Importing this module is the single composition entry point.
ensure_siblings_importable()
