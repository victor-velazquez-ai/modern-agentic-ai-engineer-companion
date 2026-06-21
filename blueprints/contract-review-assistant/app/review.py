"""The review loop — critique a flagged clause and draft a redline (agent-loop · Ch 16).

Extraction (``clause_schema``) and grounded flagging (``flags``) tell the reviewer *what* and
*why*. This module proposes the *fix*: for each flagged clause it runs the **``agent-loop``**
blueprint — the observe→decide→act→observe cycle — with a single ``draft_redline`` tool, so the
agent compares the deviating clause against the standard position from the cited playbook rule and
returns a proposed edit. The loop is *composed*, not reimplemented: we inject a scripted
:class:`~agent_loop.MockModel` (zero spend, deterministic) and the loop's hardening (turn cap,
tool-error recovery) comes for free.

The whole run is wrapped in **``observability-stack``** spans, so every flag → rule → redline is
traceable end to end — the audit posture the PLAN requires.

**Human-in-the-loop is the product.** The agent only ever *proposes*. Each redline becomes a
:class:`RedlineProposal` whose ``decision`` starts at :attr:`Decision.PENDING`; a reviewer
(``app`` / a UI) calls :meth:`RedlineProposal.accept` / ``edit`` / ``reject``. There is no
"accept all" and no auto-apply. The data model makes the lawyer the decision-maker by construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from . import _compose  # noqa: F401  -- side effect: pattern blueprints onto sys.path

# Composed pattern blueprints (imported after _compose wired sys.path).
from agent_loop import (  # noqa: E402
    AgentLoop,
    MockModel,
    ToolCall,
    ToolRegistry,
    assistant,
    tool,
)

try:  # observability is optional at runtime; degrade to a no-op tracer if absent.
    from observability_stack import SpanKind, Tracer  # noqa: E402

    _HAVE_OBS = True
except Exception:  # pragma: no cover - exercised only when the sibling is missing
    _HAVE_OBS = False

from .clause_schema import Clause  # noqa: E402
from .flags import Flag  # noqa: E402


class Decision(str, Enum):
    """Who decides — the lawyer. The agent never advances past PENDING on its own."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class RedlineProposal:
    """A proposed edit to one clause — *a proposal*, gated on a human decision.

    The agent fills ``original_text``/``proposed_text``/``rationale`` and cites the ``Flag`` that
    motivated it. ``decision`` is :attr:`Decision.PENDING` until a reviewer disposes of it; the
    three transition methods return a **new** proposal (frozen — an audit trail never edits the
    past in place), so a UI can render before/after with the human's final text.
    """

    flag: Flag
    clause_id: str
    original_text: str
    proposed_text: str
    rationale: str
    decision: Decision = Decision.PENDING
    final_text: str = ""

    def accept(self) -> "RedlineProposal":
        """Reviewer accepts the agent's proposed text verbatim."""
        return replace(self, decision=Decision.ACCEPTED, final_text=self.proposed_text)

    def edit(self, final_text: str) -> "RedlineProposal":
        """Reviewer edits the proposal — their text wins, the agent's is recorded for audit."""
        return replace(self, decision=Decision.EDITED, final_text=final_text)

    def reject(self) -> "RedlineProposal":
        """Reviewer rejects the proposal; the original clause stands unchanged."""
        return replace(self, decision=Decision.REJECTED, final_text=self.original_text)


# --- the agent-loop tool the model calls -------------------------------------------------

@tool(
    "draft_redline",
    "Propose replacement text for a non-standard clause to align it with the standard position. "
    "Call exactly once with the rewritten clause and a one-sentence rationale.",
    {
        "type": "object",
        "properties": {
            "proposed_text": {"type": "string", "description": "The rewritten clause text."},
            "rationale": {"type": "string", "description": "Why this aligns to the standard."},
        },
        "required": ["proposed_text", "rationale"],
    },
)
def _draft_redline(proposed_text: str, rationale: str) -> str:
    """The tool body just echoes a confirmation; the *arguments* are the redline we keep.

    We read the structured arguments off the transcript (not this return value), because the
    proposed edit is the model's *input* to the tool. The tool exists so the loop has a typed,
    schema-validated channel for the proposal rather than free-text parsing — the Ch 12/16 point.
    """
    return f"redline drafted ({len(proposed_text)} chars)"


def _standard_position(flag: Flag) -> str:
    """Pull the 'Standard template:'/'Standard position:' line out of the cited rule, if present."""
    for line in flag.rule_excerpt.splitlines():
        s = line.strip()
        if s.lower().startswith(("standard template:", "standard position:")):
            return s.split(":", 1)[1].strip()
    return "the standard position in the cited playbook rule"


def _build_model(flag: Flag, clause: Clause) -> MockModel:
    """Script a deterministic 'brain' that calls draft_redline once with a sensible proposal.

    This is the offline stand-in for a reasoning model (Ch 16 critique/redline). On the live path
    you inject a gateway-backed ``ModelPort`` here instead — the loop and tool are unchanged.
    """
    standard = _standard_position(flag)
    proposal = (
        f"{standard} "
        f"(Revised to resolve {flag.rule_id}: {flag.message}.)"
    )
    rationale = (
        f"Aligns the {flag.clause_type} clause to {flag.rule_id} "
        f"(severity={flag.severity}); replaces the non-standard language with the standard position."
    )
    return MockModel(
        [
            # Turn 1: the model decides to use the redline tool.
            assistant(
                text="Comparing the clause to the cited standard; drafting a redline.",
                tool_calls=(
                    ToolCall(
                        id="redline-1",
                        name="draft_redline",
                        arguments={"proposed_text": proposal, "rationale": rationale},
                    ),
                ),
            ),
            # Turn 2: after the tool result, the model produces its final (text) answer.
            lambda _t: assistant(text="Redline proposed; awaiting lawyer review."),
        ]
    )


def propose_redline(
    flag: Flag,
    clause: Clause,
    *,
    tracer: "Tracer | None" = None,
) -> RedlineProposal:
    """Run the agent-loop critique for one flagged clause and return a PENDING proposal.

    Steps, all traced when an observability tracer is active:
      1. build a scripted model + a one-tool registry (``draft_redline``);
      2. run the loop over a critique prompt that carries the clause and the cited rule;
      3. read the structured ``proposed_text``/``rationale`` off the tool call in the transcript.

    The returned proposal is always :attr:`Decision.PENDING` — the lawyer disposes of it.
    """
    registry = ToolRegistry([_draft_redline])
    loop = AgentLoop(model=_build_model(flag, clause), tools=registry, max_turns=4)

    system_prompt = (
        "You are a contract-review assistant. You PROPOSE redlines; a lawyer decides. "
        "Compare the clause to the cited standard position and draft one aligned redline. "
        "Never assert a legal conclusion without citing the provided rule."
    )
    task = (
        f"Clause ({flag.clause_type}) at {flag.clause_location}:\n{clause.text}\n\n"
        f"Cited rule {flag.rule_id} (severity {flag.severity}):\n{flag.rule_excerpt}\n\n"
        f"Issue: {flag.message}\nDraft a redline that aligns this clause to the standard."
    )

    def _run() -> "object":
        return loop.run(task, system_prompt=system_prompt)

    if tracer is not None and _HAVE_OBS:
        with tracer.span(f"redline:{clause.id}", SpanKind.CHAIN):
            result = _run()
    else:
        result = _run()

    proposed_text, rationale = _extract_proposal(result)
    return RedlineProposal(
        flag=flag,
        clause_id=clause.id,
        original_text=clause.text,
        proposed_text=proposed_text,
        rationale=rationale,
    )


def _extract_proposal(result: "object") -> tuple[str, str]:
    """Read the draft_redline arguments back off the loop's transcript.

    Falls back to empty strings if the tool was never called (a defensive default; the scripted
    model always calls it, but a live model might not — and a missing proposal must not crash the
    review, it just yields an empty proposal the reviewer will reject).
    """
    transcript = getattr(result, "transcript", None)
    if transcript is None:
        return "", ""
    for msg in transcript:
        for call in getattr(msg, "tool_calls", ()):  # assistant turns carry tool_calls
            if call.name == "draft_redline":
                args = call.arguments or {}
                return str(args.get("proposed_text", "")), str(args.get("rationale", ""))
    return "", ""


@dataclass(slots=True)
class ReviewResult:
    """The full output of reviewing one contract: clauses, flags, and pending proposals."""

    doc_id: str
    clauses: list[Clause] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)
    proposals: list[RedlineProposal] = field(default_factory=list)

    @property
    def pending(self) -> list[RedlineProposal]:
        """Proposals still awaiting a human decision (all of them, until a reviewer acts)."""
        return [p for p in self.proposals if p.decision is Decision.PENDING]
