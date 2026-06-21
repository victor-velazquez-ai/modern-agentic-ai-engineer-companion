"""The composition seam — make the *pattern* blueprints importable, without forking them.

A **solution** blueprint is not a new library: it is a recipe that *composes* the pattern
blueprints (the parts) into a product. The honest way to do that in a study-and-adapt repo
(no installed wheels) is to put each sibling pattern's ``src/`` on ``sys.path`` and import its
package directly — the same seam the other solution blueprints use. We **import**, we never
copy: a bug fixed in ``agent-loop`` (or ``eval-harness``, ``observability-stack``,
``llm-gateway``) is a bug fixed here, and the wiring you read in this folder is the whole of
the "integration".

This pipeline composes (see ``PLAN.md`` → "Composes"):

* ``agent-loop`` — the extract → validate → repair control loop (Ch 12/45).
* ``eval-harness`` — the golden-set accuracy gate that picks the cheapest passing model (Ch 22).
* ``observability-stack`` — per-item tracing + cost roll-up + dead-letter visibility (Ch 23).
* ``llm-gateway`` — model choice + metered inference for the live worker fleet (Ch 39–41).

Layout this relies on::

    blueprints/
      agent-loop/src/agent_loop/
      eval-harness/src/eval_harness/
      observability-stack/src/observability_stack/
      llm-gateway/src/llm_gateway/
      document-extraction-pipeline/pipeline/_compose.py   <- you are here

``add_pattern_blueprints_to_path()`` resolves ``blueprints/`` as ``parents[2]`` of this file
and inserts the four ``src/`` dirs (idempotently). Call it once, at the top of any module that
imports a pattern package; the ``pipeline.*`` modules below do exactly that via
``from . import _compose``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# blueprints/document-extraction-pipeline/pipeline/_compose.py
#   parents[0] = pipeline/  parents[1] = document-extraction-pipeline/  parents[2] = blueprints/
_BLUEPRINTS_DIR = Path(__file__).resolve().parents[2]

# The pattern blueprints this solution composes (PLAN.md → "Composes"). Order is irrelevant;
# each contributes one top-level package under its own ``src/``.
_PATTERNS = (
    "agent-loop",
    "eval-harness",
    "observability-stack",
    "llm-gateway",
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


# Wire the path the moment this module is imported, so a simple ``from . import _compose`` is
# enough to make the pattern packages importable from any module in this package.
add_pattern_blueprints_to_path()
