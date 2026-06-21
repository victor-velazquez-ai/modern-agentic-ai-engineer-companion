"""Make the four composed PATTERN blueprints importable — by path, not by fork.

A solution blueprint's whole point is *reuse*: it should depend on the pattern blueprints
the way a real service depends on its libraries, never by copy-pasting them. None of these
packages are installed as wheels in this teaching repo (the rule is "study & adapt, run it in
place"), so we add each sibling blueprint's ``src/`` directory to ``sys.path`` exactly once,
here, and then ``import rag_pipeline`` / ``agent_loop`` / ``eval_harness`` /
``observability_stack`` resolve to the *originals* two folders up.

If a pattern hasn't been built yet, the import fails loudly with a pointer to the folder —
far better than a silent fallback that hides which part is missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

# blueprints/compliance-monitoring-agent/app/_pattern_imports.py
#   .parent          -> app/
#   .parent.parent   -> compliance-monitoring-agent/
#   .parent.parent.parent -> blueprints/   (where the sibling patterns live)
_BLUEPRINTS = Path(__file__).resolve().parent.parent.parent

# slug -> top-level package name exposed under its src/
_PATTERNS: dict[str, str] = {
    "agent-loop": "agent_loop",
    "rag-pipeline": "rag_pipeline",
    "eval-harness": "eval_harness",
    "observability-stack": "observability_stack",
}


def ensure_patterns_importable() -> None:
    """Add each composed pattern blueprint's ``src/`` to ``sys.path`` (idempotent)."""
    for slug in _PATTERNS:
        src = _BLUEPRINTS / slug / "src"
        if not src.is_dir():
            raise ModuleNotFoundError(
                f"Pattern blueprint {slug!r} not found at {src}. "
                f"This solution composes it; build the pattern first "
                f"(see blueprints/{slug}/)."
            )
        s = str(src)
        if s not in sys.path:
            sys.path.insert(0, s)


# Resolve the seam at import time so a plain ``from app.classify import ...`` works.
ensure_patterns_importable()
