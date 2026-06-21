"""incident_response_copilot.app — the solution wiring (Appendix G; Ch 43).

A SRE/IT-ops copilot built by **composing** five pattern blueprints, never forking them:

* ``rag-pipeline``        — retrieval over runbooks + past incidents (the ``Knowledge`` retriever).
* ``mcp-server``          — read-mostly, least-privilege observability/log/deploy tools.
* ``agent-loop``          — the reasoning loop that correlates signals + proposes remediation.
* ``observability-stack`` — the incident trace that drives postmortem drafting + the audit ledger seam.
* ``eval-harness``        — evals / chaos-style testing over historical incidents (see ``evals/``).

The autonomy dial is tight on purpose: **propose-not-act** by default, a human-in-the-loop
approval gate on anything that mutates production, and dangerous verbs simply absent from the
tool set until earned. Import ``_bootstrap`` first (it puts the pattern packages on the path);
everything here is importable and runs free in MOCK mode.
"""

from __future__ import annotations

from . import _bootstrap  # noqa: F401  (side-effect: wire the composed patterns onto sys.path)

# Re-export the solution surface so callers (demo.py, evals/) import from one place. These imports
# come *after* _bootstrap so the composed pattern packages are already on sys.path.
from .triage import (  # noqa: E402
    Alert,
    ProposedAction,
    Severity,
    Triage,
    severity_from_metrics,
)
from .knowledge import Knowledge, RunbookHit, load_corpus  # noqa: E402
from .correlate import correlate  # noqa: E402
from .approve import (  # noqa: E402
    ApprovalOutcome,
    Approver,
    GateReport,
    auto_approve,
    auto_deny,
    review_and_execute,
)
from .postmortem import Postmortem, draft_postmortem  # noqa: E402

__all__ = [
    "_bootstrap",
    # triage
    "Alert",
    "ProposedAction",
    "Severity",
    "Triage",
    "severity_from_metrics",
    # knowledge (rag-pipeline)
    "Knowledge",
    "RunbookHit",
    "load_corpus",
    # correlation (agent-loop + mcp + rag + observability)
    "correlate",
    # approval gate (HITL)
    "ApprovalOutcome",
    "Approver",
    "GateReport",
    "auto_approve",
    "auto_deny",
    "review_and_execute",
    # postmortem
    "Postmortem",
    "draft_postmortem",
]
__version__ = "0.1.0"
