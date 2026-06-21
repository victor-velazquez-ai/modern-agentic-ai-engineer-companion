"""Composition seam — make the sibling *pattern* blueprints importable, without forking them.

This solution blueprint is a **composition**: it wires together five pattern blueprints that
live next to it under ``blueprints/<pattern>/src/<package>/``. The golden rule is *compose by
import, never fork* — so instead of copying their code we put each sibling's ``src/`` on
``sys.path`` and import the real package. Edit a pattern once and every solution that composes it
moves with it.

Why a path shim and not ``pip install``? Because the repo's promise is "clone and run it free
and offline" — no editable installs, no build step. Each pattern blueprint already does the same
``sys.path.insert`` trick in its own ``demo.py``; this module just centralises it for the five
packages this solution needs.

Public surface
--------------
``ensure_blueprints_on_path()`` — idempotently add the five sibling ``src/`` dirs to ``sys.path``.
``repo_root()`` / ``blueprint_dir()`` — path helpers the app and tools share.

If a sibling package has not been built yet, importing it raises a clear ``ModuleNotFoundError``
naming which blueprint to build first (these are the Phase-1 pattern packages; the PLAN lists
them).
"""

from __future__ import annotations

import sys
from pathlib import Path

# blueprints/software-engineering-agent/_blueprints.py
#   .parent            -> software-engineering-agent/
#   .parent.parent     -> blueprints/
_HERE = Path(__file__).resolve().parent
_BLUEPRINTS = _HERE.parent

# pattern-blueprint slug -> the package directory name it ships under src/
_PATTERNS: dict[str, str] = {
    "agent-loop": "agent_loop",
    "multi-agent-supervisor": "multi_agent_supervisor",
    "eval-harness": "eval_harness",
    "observability-stack": "observability_stack",
    "mcp-server": "mcp_server",
}


def blueprint_dir(slug: str) -> Path:
    """Absolute path to a sibling pattern blueprint's folder."""
    return _BLUEPRINTS / slug


def solution_dir() -> Path:
    """Absolute path to this solution blueprint's folder."""
    return _HERE


def repo_root() -> Path:
    """Absolute path to the bundled ``sample_repo/`` (the agent's target codebase)."""
    return _HERE / "sample_repo"


def ensure_blueprints_on_path() -> None:
    """Put each composed pattern blueprint's ``src/`` on ``sys.path`` (idempotent).

    Safe to call repeatedly and from any entrypoint (demo, tests, app modules). Missing
    blueprints are skipped silently here — the import that needs them raises the actionable
    error, naming the package and the build step.
    """
    for slug in _PATTERNS:
        src = _BLUEPRINTS / slug / "src"
        if src.is_dir():
            p = str(src)
            if p not in sys.path:
                sys.path.insert(0, p)
    # The target repo's own ``src/`` so the oracle can ``import textkit``.
    target_src = repo_root() / "src"
    if target_src.is_dir() and str(target_src) not in sys.path:
        sys.path.insert(0, str(target_src))
