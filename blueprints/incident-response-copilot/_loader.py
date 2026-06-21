"""Make this hyphenated blueprint directory importable as a real package.

The folder is ``incident-response-copilot`` — hyphens, so it can't be imported by that name. But
the solution's modules use ordinary relative imports (``from ..audit.ledger import AuditLedger``),
which only resolve if ``app`` / ``audit`` / ``tools`` are subpackages of one parent package. This
tiny loader bridges the gap, *without forking the composed patterns and without renaming anything
on disk*:

1. register this directory as the package ``incident_response_copilot`` (a valid identifier),
   pointing its ``__path__`` here so ``incident_response_copilot.app`` etc. resolve;
2. put the blueprint root on ``sys.path`` (so ``import audit`` / ``import tools`` also work as
   top-level, the shape ``demo.py`` uses), and the ``app/`` dir on ``sys.path`` (so the
   pattern-path bootstrap's bare ``import _bootstrap`` inside ``tools/ops_mock.py`` resolves).

Call :func:`bootstrap_package` once at the top of an entry point (``demo.py``,
``evals/run_evals.py``); it is idempotent and free.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_PKG_NAME = "incident_response_copilot"
_ROOT = Path(__file__).resolve().parent


def bootstrap_package() -> ModuleType:
    """Register the blueprint as ``incident_response_copilot`` and return the package module."""
    # Put the blueprint root and app/ on the path (idempotent).
    for p in (str(_ROOT), str(_ROOT / "app")):
        if p not in sys.path:
            sys.path.insert(0, p)

    if _PKG_NAME in sys.modules:
        return sys.modules[_PKG_NAME]

    init = _ROOT / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        _PKG_NAME, init, submodule_search_locations=[str(_ROOT)]
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"could not build a spec for {_PKG_NAME} at {init}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_PKG_NAME] = module
    spec.loader.exec_module(module)
    return module


def load_app():
    """Bootstrap the package and return the imported ``incident_response_copilot.app`` module."""
    bootstrap_package()
    return importlib.import_module(f"{_PKG_NAME}.app")
