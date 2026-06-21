"""route — the human adjudication queue (book **Ch 20 — Human-in-the-loop**).

The agent flags and routes; **a human adjudicates**. This module turns a stream of assessments
into a triaged review queue: flagged items become review tickets, ordered by severity and
confidence, with a status a human moves through (``pending`` -> ``confirmed`` / ``dismissed``).
Clear items pass through and are recorded but not queued.

This is deliberately *not* an autonomous-decision step. There is no "auto-close" path: the only
thing the agent decides is **priority and routing**, never the final compliance verdict. That
separation is the whole point of the Appendix-G framing — a monitoring agent that *decides* is a
liability; one that *routes well* multiplies a finite review team.

Pure stdlib, no model calls — routing is policy, not inference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .classify import Assessment

# Severity prior per rule family — how urgently a confirmed violation must reach a human. Tunable
# with stakeholders; insider-info / sanctions outrank an expenses paperwork issue.
_SEVERITY: dict[str, int] = {
    "COMM-03": 5,  # MNPI / insider information
    "TXN-02": 5,   # sanctions / prohibited counterparties
    "COMM-01": 4,  # customer PII exposure
    "TXN-01": 4,   # AML reporting-threshold / structuring
    "COMM-02": 3,  # guaranteed-returns / suitability
    "COMM-04": 3,  # harassment / trust-and-safety
    "TXN-03": 2,   # expense-policy
}
DEFAULT_SEVERITY = 2


class ReviewStatus(str, Enum):
    """Where a ticket is in the human review lifecycle. The agent only ever sets ``PENDING``."""

    PENDING = "pending"
    CONFIRMED = "confirmed"   # a human confirmed the violation
    DISMISSED = "dismissed"   # a human cleared it (false positive)

    def __str__(self) -> str:
        return self.value


@dataclass
class ReviewTicket:
    """A flagged item awaiting human adjudication.

    Carries everything the adjudicator needs to act *without* re-investigating: the item, the
    cited rule + its text (the basis), the agent's confidence, and a computed priority. ``status``
    starts ``PENDING``; :meth:`adjudicate` is the human's move.
    """

    item_id: str
    item_text: str
    rule_id: str
    rule_title: str
    basis: str
    confidence: float
    severity: int
    status: ReviewStatus = ReviewStatus.PENDING
    resolution_note: str = ""

    @property
    def priority(self) -> float:
        """Higher = review sooner. Severity dominates; confidence breaks ties within a band."""
        return self.severity + self.confidence

    def adjudicate(self, confirmed: bool, note: str = "") -> "ReviewTicket":
        """The human's decision — confirm the violation or dismiss it as a false positive."""
        self.status = ReviewStatus.CONFIRMED if confirmed else ReviewStatus.DISMISSED
        self.resolution_note = note
        return self


@dataclass
class AdjudicationQueue:
    """An ordered queue of review tickets for the compliance team.

    The agent only ever *enqueues* (``PENDING``); humans call :meth:`adjudicate`. The queue keeps
    itself ordered by priority so the most serious, highest-confidence flags surface first.
    """

    tickets: list[ReviewTicket] = field(default_factory=list)

    def enqueue(
        self,
        *,
        item_id: str,
        item_text: str,
        assessment: Assessment,
        rule_title: str,
        basis: str,
    ) -> ReviewTicket:
        """Create and file a review ticket from a flagged assessment. Returns the ticket."""
        ticket = ReviewTicket(
            item_id=item_id,
            item_text=item_text,
            rule_id=assessment.rule_id,
            rule_title=rule_title,
            basis=basis,
            confidence=assessment.confidence,
            severity=_SEVERITY.get(assessment.rule_id, DEFAULT_SEVERITY),
        )
        self.tickets.append(ticket)
        self.tickets.sort(key=lambda t: (-t.priority, t.item_id))
        return ticket

    @property
    def pending(self) -> list[ReviewTicket]:
        """Tickets still awaiting a human, highest priority first."""
        return [t for t in self.tickets if t.status is ReviewStatus.PENDING]

    def __len__(self) -> int:
        return len(self.tickets)


def severity_for(rule_id: str) -> int:
    """Public accessor for a rule's severity prior (used by the demo + tunable by stakeholders)."""
    return _SEVERITY.get(rule_id, DEFAULT_SEVERITY)
