"""Wire the sibling *pattern* blueprints onto ``sys.path`` so this solution can COMPOSE them.

The golden rule for solution blueprints (see ``blueprints/README.md``) is **compose, do not
fork**: this folder imports the agent-loop, rag-pipeline, eval-harness, and observability-stack
packages by relative path and reuses them unchanged. Nothing here re-implements a pattern.

Each pattern blueprint ships its package under ``<pattern>/src/<pkg>``; we add those ``src``
directories to ``sys.path`` exactly the way every pattern's own ``demo.py`` does, so the solution
runs straight from a clone (before any ``pip install -e .``). Importing this module for its side
effect is all the wiring a composing module needs::

    import _compose  # noqa: F401  (puts the four pattern packages on sys.path)
    from agent_loop import AgentLoop
    from rag_pipeline import HybridRetriever
"""

from __future__ import annotations

import sys
from pathlib import Path

# blueprints/text-to-sql-analytics/app/_compose.py -> blueprints/
_BLUEPRINTS = Path(__file__).resolve().parents[2]

# The four pattern blueprints this solution composes (PLAN.md -> "Composes").
_PATTERNS = (
    "agent-loop",
    "rag-pipeline",
    "eval-harness",
    "observability-stack",
)


def wire_patterns() -> list[str]:
    """Prepend each pattern blueprint's ``src/`` to ``sys.path``; return the paths added.

    Idempotent: a path already present is not added again. Missing patterns are skipped
    silently rather than raising, so the module stays importable even in a partial checkout —
    the import of the missing package is what will fail loudly, with a clear name.
    """
    added: list[str] = []
    for pattern in _PATTERNS:
        src = _BLUEPRINTS / pattern / "src"
        if src.is_dir() and str(src) not in sys.path:
            sys.path.insert(0, str(src))
            added.append(str(src))
    return added


# Wire on import — importing this module is the whole point.
wire_patterns()
