"""Put the composed pattern blueprints on ``sys.path`` for the :mod:`tenancy` package.

``tenancy`` is a sibling of ``app``, and ``app._compose`` already owns the single, tested
implementation of "find ``blueprints/`` and insert each pattern's ``src/``". Rather than
duplicate that logic (which would be a fork of exactly the kind this repo avoids), we make
``blueprints/`` importable as a package root, then defer to ``app._compose``.

Importing this module is the side effect: ``from . import _patch_path`` at the top of any
``tenancy`` module that imports ``rag_pipeline`` (etc.) is enough.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

# tenancy/_patch_path.py → parents[1] = product-copilot/ (the solution blueprint root).
_BLUEPRINT_ROOT = Path(__file__).resolve().parents[1]

# Make ``app`` importable so we can reuse its composition seam regardless of how the caller
# entered (``python demo.py`` from the blueprint folder, or ``import tenancy`` from a test that
# only added the blueprint root to the path).
_root = str(_BLUEPRINT_ROOT)
if _root not in sys.path:
    sys.path.insert(0, _root)

# Importing ``app._compose`` runs ``add_pattern_blueprints_to_path()`` as a side effect, which
# puts agent_loop / rag_pipeline / llm_gateway / eval_harness / observability_stack on the path.
importlib.import_module("app._compose")
