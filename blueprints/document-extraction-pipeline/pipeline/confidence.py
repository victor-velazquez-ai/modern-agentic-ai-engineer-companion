"""Confidence scoring and human-review routing (Ch 20).

Passing schema validation means the output is *well-typed*, not that it is *correct*. An
invoice can be perfectly shaped and still wrong: the OCR read ``8`` as ``3``, dropped a line,
or the vendor name is mangled. The expensive, lawsuit-shaped errors live exactly here — in the
last 20% that looks fine but isn't — so a serious pipeline does **not** auto-post every valid
extraction. It scores confidence and routes anything below a written threshold to a human
review queue.

This module computes a confidence score from cheap, deterministic signals (no extra model
call) and applies the routing decision. The signals are illustrative; the discipline is the
point — **decide the accepted error rate and the review path up front, in writing.** The
threshold is the dial finance signs off on, and the eval-harness golden set (``evals/``) is how
you set it honestly rather than by vibe.

Decisions
---------
* ``ACCEPT``  — confidence ≥ ``accept_threshold``; safe to write to the system of record.
* ``REVIEW``  — below threshold; goes to the :class:`ReviewQueue` for a human to confirm/fix.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .schema import Invoice, reconciliation_gap


class Decision(str, Enum):
    ACCEPT = "accept"
    REVIEW = "review"

    def __str__(self) -> str:
        return self.value


# Default bar. Tune against the golden set, not by feel — and write it down with finance.
DEFAULT_ACCEPT_THRESHOLD = 0.75


@dataclass(frozen=True, slots=True)
class ConfidenceReport:
    """The confidence score for one extraction plus the routing decision and why."""

    score: float
    decision: Decision
    signals: dict[str, float] = field(default_factory=dict)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def needs_review(self) -> bool:
        return self.decision is Decision.REVIEW


def score_confidence(
    invoice: Invoice,
    *,
    repaired: bool = False,
    accept_threshold: float = DEFAULT_ACCEPT_THRESHOLD,
) -> ConfidenceReport:
    """Score an extracted invoice in ``[0, 1]`` and decide accept-vs-review.

    Signals (each subtracts from a starting 1.0):

    * **reconciliation** — line items that don't sum to the stated total are the strongest cheap
      signal that a row was misread or dropped.
    * **repaired** — needing a repair turn is mild evidence the document was hard; weight it
      lightly so a clean repair isn't punished out of auto-accept.
    * **sparsity** — a one-line invoice with a large total is more likely a partial read.

    Returns a :class:`ConfidenceReport`; the caller routes ``REVIEW`` items to the queue.
    """
    signals: dict[str, float] = {}
    reasons: list[str] = []
    score = 1.0

    gap = reconciliation_gap(invoice)
    signals["reconciliation_gap"] = round(gap, 4)
    if gap > 0.10:
        score -= 0.40
        reasons.append(f"line items miss the total by {gap:.0%}")
    elif gap > 0.02:
        score -= 0.15
        reasons.append(f"line items miss the total by {gap:.0%}")

    if repaired:
        score -= 0.10
        reasons.append("required a repair turn")
        signals["repaired"] = 1.0

    if len(invoice.line_items) <= 1 and invoice.total >= 1000:
        score -= 0.15
        reasons.append("single line item on a large total (possible partial read)")
        signals["sparse_large"] = 1.0

    score = max(0.0, min(1.0, score))
    decision = Decision.ACCEPT if score >= accept_threshold else Decision.REVIEW
    if decision is Decision.REVIEW and not reasons:
        reasons.append(f"confidence {score:.2f} below threshold {accept_threshold:.2f}")

    return ConfidenceReport(
        score=round(score, 4),
        decision=decision,
        signals=signals,
        reasons=tuple(reasons),
    )


@dataclass(slots=True)
class ReviewItem:
    """One queued item awaiting human confirmation."""

    doc_id: str
    record: dict[str, Any]
    score: float
    reasons: tuple[str, ...]


@dataclass(slots=True)
class ReviewQueue:
    """The human-in-the-loop queue — the deliberate, written escape hatch (Ch 20).

    In production this is a durable queue (a DB table, an SQS topic) feeding a review UI. Here
    it is an in-memory list with the same surface so the demo and tests can assert on what got
    routed for human eyes versus auto-posted.
    """

    items: list[ReviewItem] = field(default_factory=list)

    def enqueue(self, doc_id: str, invoice: Invoice, report: ConfidenceReport) -> ReviewItem:
        item = ReviewItem(
            doc_id=doc_id,
            record=invoice.to_record(),
            score=report.score,
            reasons=report.reasons,
        )
        self.items.append(item)
        return item

    def __len__(self) -> int:
        return len(self.items)
