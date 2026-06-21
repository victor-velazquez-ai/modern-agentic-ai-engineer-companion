"""The structured decision the agent emits for every ticket (Ch 15 — structured output).

A support agent's output is not free text — it is a *decision* the rest of the system acts on.
Forcing that decision into a small, typed schema is what makes the agent auditable, testable,
and safe to wire to real account actions. Every ticket resolves to exactly one of three verbs:

* ``RESOLVE`` — answer the question, grounded in retrieved help-center content, with citations.
* ``ACT``     — perform a low-risk account change (reset a password, issue an in-policy refund,
  change a plan, check an order) through a scoped, gated tool, then confirm.
* ``ESCALATE``— hand off to a human, with a reason, because policy says the agent must not
  proceed (abuse, anger, an out-of-policy or irreversible request, or low retrieval confidence).

The schema is deliberately tiny and JSON-serialisable so it can be:
  * the thing the ``eval-harness`` grades (``action`` and ``citations`` are checkable fields),
  * the thing a UI renders (answer + sources, or an escalation banner), and
  * the thing an audit log stores verbatim.

This module has no model and no I/O — it is the *contract*, not the policy. ``policies.py``
decides *when* to escalate; ``support_agent.py`` decides *how* to fill these fields in.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Action(str, Enum):
    """The three terminal moves a support turn can make (the autonomy dial's rungs)."""

    RESOLVE = "resolve"     # answer-only: grounded, cited deflection
    ACT = "act"             # took a scoped, low-risk account action
    ESCALATE = "escalate"   # handed off to a human

    def __str__(self) -> str:  # so f-strings / JSON read "resolve", not "Action.RESOLVE"
        return self.value


@dataclass(frozen=True, slots=True)
class Citation:
    """A single grounding source behind a ``RESOLVE`` answer.

    ``doc_id`` ties the claim back to a help-center document so a reviewer (and the eval set)
    can verify the answer is sourced, not hallucinated. ``title`` is for display; ``score`` is
    the retriever/reranker confidence that put this source in the answer.
    """

    doc_id: str
    title: str
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"doc_id": self.doc_id, "title": self.title, "score": round(self.score, 4)}


@dataclass(frozen=True, slots=True)
class Decision:
    """The full, structured outcome of one ticket — the agent's only output shape.

    Exactly one ``action``; the other fields are populated as that action needs:

    * ``RESOLVE`` → ``answer`` (the reply) + ``citations`` (≥1 source; an uncited answer is a
      bug an eval should catch).
    * ``ACT``     → ``answer`` (the confirmation) + ``tool`` / ``tool_args`` / ``tool_result``
      (what was done, via which scoped tool).
    * ``ESCALATE``→ ``escalation_reason`` (why a human is needed); ``answer`` may hold a holding
      message for the customer.

    ``confidence`` is the agent's own [0,1] read on the turn (retrieval strength for RESOLVE,
    policy certainty for ESCALATE) — useful for the autonomy dial and for routing review.
    """

    action: Action
    answer: str = ""
    citations: tuple[Citation, ...] = field(default_factory=tuple)
    tool: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_result: Any = None
    escalation_reason: str = ""
    confidence: float = 0.0

    # --- ergonomic constructors (intent reads clearly at the call site) -----------------
    @classmethod
    def resolve(
        cls,
        answer: str,
        citations: tuple[Citation, ...] = (),
        *,
        confidence: float = 0.0,
    ) -> "Decision":
        return cls(
            action=Action.RESOLVE,
            answer=answer,
            citations=tuple(citations),
            confidence=confidence,
        )

    @classmethod
    def act(
        cls,
        answer: str,
        *,
        tool: str,
        tool_args: dict[str, Any] | None = None,
        tool_result: Any = None,
        citations: tuple[Citation, ...] = (),
        confidence: float = 0.0,
    ) -> "Decision":
        return cls(
            action=Action.ACT,
            answer=answer,
            tool=tool,
            tool_args=dict(tool_args or {}),
            tool_result=tool_result,
            citations=tuple(citations),
            confidence=confidence,
        )

    @classmethod
    def escalate(
        cls,
        reason: str,
        *,
        answer: str = "",
        confidence: float = 0.0,
    ) -> "Decision":
        return cls(
            action=Action.ESCALATE,
            answer=answer or "I'm connecting you with a member of our team who can help.",
            escalation_reason=reason,
            confidence=confidence,
        )

    # --- read / serialise ----------------------------------------------------------------
    @property
    def cited(self) -> bool:
        """A RESOLVE answer must carry at least one source; everything else is ``cited`` n/a."""
        return bool(self.citations)

    def source_ids(self) -> list[str]:
        """The doc ids backing this decision (what an eval checks the answer is grounded in)."""
        return [c.doc_id for c in self.citations]

    def to_dict(self) -> dict[str, Any]:
        """A JSON-serialisable view — the audit-log / eval / API shape."""
        return {
            "action": str(self.action),
            "answer": self.answer,
            "citations": [c.to_dict() for c in self.citations],
            "tool": self.tool,
            "tool_args": self.tool_args,
            "tool_result": self.tool_result,
            "escalation_reason": self.escalation_reason,
            "confidence": round(self.confidence, 4),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    def headline(self) -> str:
        """A one-line summary for the console/trace (what happened, at a glance)."""
        if self.action is Action.RESOLVE:
            srcs = ", ".join(self.source_ids()) or "(uncited!)"
            return f"RESOLVE  · sources=[{srcs}]  conf={self.confidence:.2f}"
        if self.action is Action.ACT:
            return f"ACT      · tool={self.tool} args={self.tool_args}  conf={self.confidence:.2f}"
        return f"ESCALATE · reason={self.escalation_reason!r}  conf={self.confidence:.2f}"
