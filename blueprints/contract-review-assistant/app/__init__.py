"""contract-review-assistant — a SOLUTION blueprint (Appendix G #4).

This package is a *recipe*, not a new library: it **composes** four pattern blueprints into a
contract-review assistant that proposes, while a lawyer disposes.

* ``clause_schema`` — validated clause/term extraction (Ch 15).
* ``flags``         — grounded, **cited** deviation flags via the ``rag-pipeline`` blueprint (Ch 13).
* ``review``        — clause-by-clause critique + redline draft via the ``agent-loop`` blueprint
                      (Ch 16), traced with ``observability-stack`` (Ch 23); every redline is a
                      *pending* proposal the human decides on.

The one public entry point is :func:`review_contract`. Everything runs **offline and free** under
``COMPANION_MOCK=1`` (the default); no module imports an SDK or spends tokens by default.
"""

from __future__ import annotations

from . import _compose  # noqa: F401  -- side effect: pattern blueprints onto sys.path

from .clause_schema import (  # noqa: E402
    Clause,
    ClauseType,
    ClauseValidationError,
    extract_clauses,
    validate_clause,
)
from .flags import (  # noqa: E402
    Flag,
    PlaybookIndex,
    PlaybookRule,
    flag_clause,
    flag_clauses,
    load_playbook_rules,
)
from .review import (  # noqa: E402
    Decision,
    RedlineProposal,
    ReviewResult,
    propose_redline,
)

__all__ = [
    # extraction
    "Clause",
    "ClauseType",
    "ClauseValidationError",
    "extract_clauses",
    "validate_clause",
    # flagging (rag-grounded, cited)
    "Flag",
    "PlaybookRule",
    "PlaybookIndex",
    "load_playbook_rules",
    "flag_clause",
    "flag_clauses",
    # review / redline (agent-loop, HITL)
    "Decision",
    "RedlineProposal",
    "ReviewResult",
    "propose_redline",
    # orchestration
    "review_contract",
]

__version__ = "0.1.0"


def review_contract(
    doc_id: str,
    contract_text: str,
    *,
    index: "PlaybookIndex | None" = None,
    tracer: object | None = None,
) -> "ReviewResult":
    """Run the whole pipeline on one contract and return a :class:`ReviewResult`.

    extract → flag (cited) → propose redline (pending). The result's ``proposals`` are all
    :attr:`Decision.PENDING`: this function *never* accepts anything — the lawyer does, by calling
    ``proposal.accept()/edit()/reject()`` on the returned proposals.

    Args:
        doc_id: stable id for the contract (used in clause/flag ids).
        contract_text: the raw contract text.
        index: a prebuilt :class:`PlaybookIndex` (build once, reuse across many contracts). One is
            constructed on demand if omitted.
        tracer: an optional ``observability_stack.Tracer`` for an end-to-end audit trace.
    """
    idx = index if index is not None else PlaybookIndex()
    clauses = extract_clauses(doc_id, contract_text)
    flags = flag_clauses(clauses, idx)

    by_id = {c.id: c for c in clauses}
    proposals = [
        propose_redline(flag, by_id[flag.clause_id], tracer=tracer)
        for flag in flags
        if flag.clause_id in by_id
    ]
    return ReviewResult(doc_id=doc_id, clauses=clauses, flags=flags, proposals=proposals)
