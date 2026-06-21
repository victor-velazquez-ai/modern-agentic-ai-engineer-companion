"""product-copilot — a customer-facing, in-app product copilot (solution blueprint).

This package *composes* the pattern blueprints (it never forks them):

* ``rag_pipeline``        — retrieval over product docs **and** the user's own scoped data.
* ``llm_gateway``         — tiered routing, caching, per-user limits, abuse guards (the margin).
* ``agent_loop``          — the in-app agent that answers and acts **as the signed-in user**.
* ``eval_harness``        — task-success + online-feedback checks.
* ``observability_stack`` — latency, cost-per-user, and abuse signals on the public surface.

Importing this package wires the sibling ``src/`` dirs onto ``sys.path`` (see :mod:`._compose`),
so ``from app.copilot import Copilot`` just works when you run from the blueprint folder with no
install. Everything runs **offline with zero API spend** under ``COMPANION_MOCK=1`` (the repo
default).
"""

from __future__ import annotations

from . import _compose  # noqa: F401  (side effect: put pattern blueprints on sys.path)

__all__ = ["_compose"]
__version__ = "0.1.0"
