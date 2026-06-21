"""incident-response-copilot — a *solution* blueprint that composes five pattern blueprints.

This package bundles the solution's subpackages — :mod:`app` (the wiring), :mod:`audit` (the
append-only ledger), and :mod:`tools` (the least-privilege ops tools) — under one importable
namespace so their relative imports (``from ..audit.ledger import ...``) resolve cleanly.

The folder name on disk is ``incident-response-copilot`` (hyphens), which is not a valid Python
identifier, so the entry points (``demo.py``, ``evals/run_evals.py``) register this directory as
the importable package ``incident_response_copilot`` via :mod:`_loader` before importing it. That
keeps the composed pattern blueprints un-forked: every ``import agent_loop`` / ``rag_pipeline`` /
``mcp_server`` / ``eval_harness`` / ``observability_stack`` still resolves to the one canonical
copy two directories up (see ``app/_bootstrap.py``).
"""

from __future__ import annotations

__version__ = "0.1.0"
