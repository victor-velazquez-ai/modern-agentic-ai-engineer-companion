"""customer-support-agent — a SOLUTION blueprint that *composes* pattern blueprints.

Appendix G use case #1 ("Customer-support agent"). A front-line agent that **deflects**
repetitive questions with grounded, cited answers (``rag-pipeline``), **acts** on low-risk
account changes through scoped, least-privilege tools (``mcp-server``) driven by a tool-use
loop (``agent-loop``), and **escalates** to a human when policy says it must not proceed —
all gated by an eval set (``eval-harness``) and traceable (``observability-stack``).

Nothing here forks a pattern blueprint: :mod:`app._paths` puts each sibling's ``src/`` on the
path and we import the published packages. Runs free, offline, and deterministically in MOCK
mode (``COMPANION_MOCK=1``, the default); the live path routes turns through ``llm-gateway``.
"""

from __future__ import annotations

from . import _paths  # noqa: F401  (side effect: make sibling blueprints importable)

__all__ = ["_paths"]
__version__ = "0.1.0"
