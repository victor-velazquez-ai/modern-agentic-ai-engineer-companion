"""Composition seam — make the *pattern* blueprints importable without forking them.

A solution blueprint is supposed to **compose** the pattern blueprints, not copy them. Each
pattern blueprint ships its code under its own ``src/`` (e.g. ``../agent-loop/src/agent_loop``).
This module puts those ``src/`` directories on ``sys.path`` so this package can simply::

    from agent_loop import AgentLoop
    from rag_pipeline import HybridRetriever
    from mcp_server import build_default_server
    from eval_harness import run, gate
    from observability_stack import Tracer

…and the code that runs is the *one* copy living in the sibling blueprint. Change a pattern
blueprint and this solution picks the change up; there is no fork to keep in sync. (The pattern
demos do the same ``sys.path.insert(... / "src")`` shim to run straight from a clone before any
``pip install -e .`` — we reuse exactly that convention here, once, for every sibling.)

This is import plumbing only: no network, no model, no API spend. Import it for its side effect
(``import app._paths``) before importing any sibling package, or call :func:`ensure_on_path`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# This file lives at  customer-support-agent/app/_paths.py
# Sibling pattern blueprints live at  blueprints/<pattern>/src/<package>
_BLUEPRINTS_DIR = Path(__file__).resolve().parents[2]

# The pattern blueprints this solution composes (PLAN.md → "Composes"). Each maps to a
# ``<blueprint>/src`` directory that holds its importable package.
_PATTERN_BLUEPRINTS = (
    "agent-loop",
    "rag-pipeline",
    "mcp-server",
    "eval-harness",
    "observability-stack",
    "llm-gateway",  # reused on the live path (routing easy vs. hard turns); optional in MOCK
)


def ensure_on_path() -> list[str]:
    """Insert each sibling blueprint's ``src/`` onto ``sys.path`` (idempotent).

    Returns the list of paths that are now importable, so a caller (or a test) can assert the
    composition wiring is intact. A missing sibling is skipped silently rather than raising —
    the only hard dependency for the MOCK demo's *happy path* is checked where it is used.
    """
    added: list[str] = []
    for slug in _PATTERN_BLUEPRINTS:
        src = _BLUEPRINTS_DIR / slug / "src"
        if src.is_dir():
            p = str(src)
            if p not in sys.path:
                sys.path.insert(0, p)
            added.append(p)
    return added


# Import side effect: wiring the path is the whole point of importing this module.
ensure_on_path()
