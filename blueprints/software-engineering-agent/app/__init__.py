"""software_engineering_agent.app — the SOLUTION blueprint, assembled from pattern blueprints.

This is the Appendix-G **software-engineering agent**: agents pointed at the software-development
lifecycle (code review, fix generation, large-scale migrations) where **the test suite and CI are
the verification loop** — a generated change is accepted only if the oracle goes green, and a human
still owns the merge.

It is deliberately thin. The mechanisms live in five sibling **pattern blueprints**, imported (not
forked) via :mod:`_blueprints`:

* ``agent-loop``             — the per-task read-code → propose-diff → run-oracle loop (Ch 12, 16).
* ``multi-agent-supervisor`` — fan a migration across many files/call sites (Ch 17).
* ``eval-harness``           — **CI *is* the eval**: ``ci/oracle.py`` scores each change (Ch 22).
* ``observability-stack``    — trace each agent run; attach the oracle verdict (Ch 23).
* ``mcp-server``             — the sandboxed, least-privilege repo toolset (Ch 12, 41).

Everything runs **free and offline in MOCK mode** (``COMPANION_MOCK=1``, the default): no API key,
no spend, deterministic output, **never an auto-merge**. The entry points:

* :class:`CodeAgent` — fix one failing test behind the oracle, then emit a :class:`PullRequest`.
* :class:`Migration` — rewrite a deprecated API across the repo behind a resumable manifest.
* :class:`PullRequest` — the structured diff a human reviews and merges (or rejects).

See :mod:`app.code_agent`, :mod:`app.migrate`, :mod:`app.pr`, and the top-level ``demo.py``.
"""

from __future__ import annotations

from .code_agent import (
    CodeAgent,
    FixAttempt,
    build_agent,
)
from .migrate import (
    FileTask,
    Migration,
    MigrationManifest,
    MigrationResult,
    build_migration,
    rename_call_sites,
)
from .pr import (
    FileDiff,
    PullRequest,
    unified_diff,
)

__all__ = [
    # code_agent (composes agent-loop + eval-harness + mcp-server + observability)
    "CodeAgent",
    "FixAttempt",
    "build_agent",
    # migrate (composes multi-agent-supervisor over a resumable manifest)
    "Migration",
    "MigrationManifest",
    "MigrationResult",
    "FileTask",
    "build_migration",
    "rename_call_sites",
    # pr (structured diff for human review — never auto-merge)
    "PullRequest",
    "FileDiff",
    "unified_diff",
]

__version__ = "0.1.0"
