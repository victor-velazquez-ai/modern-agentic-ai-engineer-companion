"""The composition seam — make the *pattern* blueprints importable, without forking them.

A **solution** blueprint is not a new library: it is a recipe that *composes* the pattern
blueprints (the parts) into a product. The honest way to do that in a study-and-adapt repo
(no installed wheels) is to put each sibling pattern's ``src/`` on ``sys.path`` and import its
package directly — the exact same seam ``rag_pipeline.embed._try_gateway_embedder`` uses to
borrow the gateway. We **import**, we never copy: a bug fixed in ``agent-loop`` is a bug fixed
here, and the wiring you read below is the whole of the "integration".

Layout this relies on::

    blueprints/
      agent-loop/src/agent_loop/
      rag-pipeline/src/rag_pipeline/
      eval-harness/src/eval_harness/
      observability-stack/src/observability_stack/
      contract-review-assistant/app/_compose.py   <- you are here

``add_pattern_blueprints_to_path()`` resolves ``blueprints/`` as ``parents[2]`` of this file
and inserts the four ``src/`` dirs (idempotently). Call it once, at the top of any module that
imports a pattern package; ``app.review`` and ``app.flags`` do exactly that.
"""

from __future__ import annotations

import sys
from pathlib import Path

# blueprints/contract-review-assistant/app/_compose.py
#   parents[0] = app/  parents[1] = contract-review-assistant/  parents[2] = blueprints/
_BLUEPRINTS_DIR = Path(__file__).resolve().parents[2]

# The pattern blueprints this solution composes (PLAN.md → "Composes"). Order is irrelevant;
# each contributes one top-level package under its own ``src/``.
_PATTERNS = (
    "agent-loop",
    "rag-pipeline",
    "eval-harness",
    "observability-stack",
)


def add_pattern_blueprints_to_path() -> list[str]:
    """Put each composed pattern's ``src/`` on ``sys.path`` (idempotent).

    Returns the list of ``src`` paths that exist and were ensured-present, so a caller (or a
    test) can assert the wiring resolved. A missing sibling is skipped silently here and
    surfaced as a normal ``ImportError`` at the actual import site, with a clear message — we
    do not want this helper to fail just because one optional pattern is absent.
    """
    ensured: list[str] = []
    for pattern in _PATTERNS:
        src = _BLUEPRINTS_DIR / pattern / "src"
        if src.is_dir():
            s = str(src)
            if s not in sys.path:
                sys.path.insert(0, s)
            ensured.append(s)
    return ensured


# Wire the path the moment this module is imported, so a simple ``import app._compose`` (or any
# module that does ``from . import _compose``) is enough to make the pattern packages importable.
add_pattern_blueprints_to_path()
