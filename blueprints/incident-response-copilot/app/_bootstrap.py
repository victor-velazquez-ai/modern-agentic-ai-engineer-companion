"""Put the five composed pattern blueprints on the import path — *without forking them*.

A solution blueprint **composes** pattern blueprints; it does not copy their code. The honest
way to do that from a clone (before anyone runs ``pip install -e``) is to add each sibling
pattern's ``src/`` directory to ``sys.path`` exactly once, then ``import`` the package by its
real name. Every ``import agent_loop`` / ``rag_pipeline`` / ``mcp_server`` / ``eval_harness`` /
``observability_stack`` in this blueprint resolves to the *one* canonical copy two directories
up — so a fix in a pattern is a fix here, and there is no second copy to drift.

Layout this relies on::

    blueprints/
    ├── agent-loop/src/agent_loop/
    ├── rag-pipeline/src/rag_pipeline/
    ├── mcp-server/src/mcp_server/
    ├── eval-harness/src/eval_harness/
    ├── observability-stack/src/observability_stack/
    └── incident-response-copilot/app/_bootstrap.py   <- you are here

Import this module (``from . import _bootstrap``  or  ``import _bootstrap``) before importing any
pattern package. It is idempotent and free: it only mutates ``sys.path``, never spends, never
imports a pattern eagerly.
"""

from __future__ import annotations

import sys
from pathlib import Path

# .../blueprints/incident-response-copilot/app/_bootstrap.py
#  parents[0] = app/  parents[1] = incident-response-copilot/  parents[2] = blueprints/
_BLUEPRINTS = Path(__file__).resolve().parents[2]

# The pattern blueprints this solution composes (PLAN.md → "Composes").
_PATTERNS: tuple[str, ...] = (
    "agent-loop",
    "rag-pipeline",
    "mcp-server",
    "eval-harness",
    "observability-stack",
)


def ensure_patterns_on_path() -> list[str]:
    """Add each composed pattern's ``src/`` to ``sys.path`` (idempotent). Returns the dirs added.

    A missing pattern directory is skipped silently rather than raising: the demo prints which
    packages it could resolve, so a partial checkout degrades to a clear message instead of an
    ``ImportError`` traceback at module load.
    """
    added: list[str] = []
    for pattern in _PATTERNS:
        src = _BLUEPRINTS / pattern / "src"
        if src.is_dir():
            s = str(src)
            if s not in sys.path:
                sys.path.insert(0, s)
            added.append(s)
    return added


# Run on import so a plain ``import _bootstrap`` is enough to wire the path.
ensure_patterns_on_path()
