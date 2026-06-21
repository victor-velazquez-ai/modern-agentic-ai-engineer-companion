"""compliance-monitoring-agent — a SOLUTION blueprint that *composes* pattern blueprints.

This package is the wiring, not new mechanism. It imports four sibling **pattern blueprints**
by their public surface and assembles them into the Appendix-G "Compliance & monitoring agent":

* ``rag-pipeline``         -> retrieval over the policy corpus, so every flag cites the rule it
                              broke (``policy_check``).
* ``agent-loop``           -> the classify -> policy-check -> route pass as a structured,
                              confidence-bearing decision (``classify`` / ``route``).
* ``observability-stack``  -> the trace + the append-only audit ledger of every decision and its
                              basis (``audit.ledger``).
* ``eval-harness``         -> the precision/recall-tuned golden set the screener is measured on
                              (``evals/``).

The composition seam is :func:`add_blueprint_paths`, which puts each sibling blueprint's ``src/``
on ``sys.path`` *without forking it*. We depend on the patterns' published ``__all__`` only — if a
pattern changes its internals, this solution keeps working as long as its public surface holds.

Everything runs **free and offline** under ``COMPANION_MOCK=1`` (the default): the patterns fall
back to their deterministic mocks (hash embedder, scripted model, console exporter), so the demo
screens the stream, flags with citations, and writes audit entries with zero API spend.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# The four pattern blueprints this solution composes. Names match their ``src/<pkg>`` dirs.
COMPOSED_PATTERNS: tuple[str, ...] = (
    "agent-loop",
    "rag-pipeline",
    "eval-harness",
    "observability-stack",
)


def add_blueprint_paths(patterns: tuple[str, ...] = COMPOSED_PATTERNS) -> list[str]:
    """Put each composed pattern blueprint's ``src/`` on ``sys.path`` (idempotent).

    A solution blueprint *composes by relative import* rather than vendoring code: the pattern
    packages live one directory up (``blueprints/<pattern>/src``), so we add those ``src/`` dirs
    to the import path. This is the same seam ``rag-pipeline`` itself uses to borrow the gateway
    embedder — sibling ``src`` on the path, import by public name, never copy the source.

    Returns the list of paths actually added (those that exist and were not already present), so a
    caller can see exactly what was wired in.
    """
    blueprints_root = Path(__file__).resolve().parents[2]  # .../blueprints/
    added: list[str] = []
    for name in patterns:
        src = blueprints_root / name / "src"
        if src.is_dir():
            s = str(src)
            if s not in sys.path:
                sys.path.insert(0, s)
                added.append(s)
    return added


def mock_mode() -> bool:
    """True when running offline/free (the default). Honors the repo-wide ``COMPANION_MOCK``."""
    return os.getenv("COMPANION_MOCK", "1") != "0"


# Wire the composed patterns onto the path at import time so ``from app.classify import ...``
# just works whether you run ``python demo.py`` or import the package in a notebook.
add_blueprint_paths()

__all__ = ["COMPOSED_PATTERNS", "add_blueprint_paths", "mock_mode"]
