"""Draft the postmortem from the incident trace + audit ledger (Ch 23, 28).

The postmortem is the institutional-memory flywheel: every incident the copilot helps resolve
should leave behind a written record that makes the *next* one faster. The expensive, error-prone
part of writing one — reconstructing "what actually happened, in order, and who decided what" — is
exactly what the **observability trace** (``observability-stack``) and the **append-only audit
ledger** (Ch 28) already captured. So this module does not ask a model to *remember* the incident;
it *reads the trace and the ledger* and renders them into a structured draft a human edits and
ships.

That ordering matters: a postmortem grounded in the recorded trace cannot hallucinate a step that
never ran, and the audit ledger's approve/reject lines mean the "decisions" section is evidence,
not recollection. In MOCK mode this is fully deterministic (no model call). On the live path you
would hand this same structured material to a gateway-backed summarizer for the prose narrative —
the *facts* still come from the trace, never from the model's memory.

Output is Markdown: cheap to diff, easy to paste into an incident tracker, and the shape an SRE
team already reviews.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import _bootstrap  # noqa: F401  (wire the composed patterns onto sys.path)

from observability_stack import Span, Trace  # noqa: E402

from ..audit.ledger import AuditLedger  # noqa: E402
from .approve import GateReport  # noqa: E402
from .triage import Triage  # noqa: E402


@dataclass(frozen=True, slots=True)
class Postmortem:
    """A structured, human-editable postmortem draft."""

    title: str
    severity: str
    summary: str
    timeline: tuple[str, ...]
    root_cause: str
    actions_taken: tuple[str, ...]
    follow_ups: tuple[str, ...]

    def to_markdown(self) -> str:
        """Render the draft as Markdown for an incident tracker."""
        lines = [
            f"# Postmortem — {self.title}",
            "",
            f"**Severity:** {self.severity}",
            "",
            "## Summary",
            self.summary,
            "",
            "## Timeline",
        ]
        lines += [f"- {t}" for t in self.timeline] or ["- (no recorded steps)"]
        lines += [
            "",
            "## Root cause",
            self.root_cause,
            "",
            "## Actions taken",
        ]
        lines += [f"- {a}" for a in self.actions_taken] or ["- (none)"]
        lines += [
            "",
            "## Follow-ups",
        ]
        lines += [f"- [ ] {f}" for f in self.follow_ups] or ["- [ ] (none identified)"]
        lines += [
            "",
            "---",
            "_Draft generated from the incident trace + audit ledger. "
            "Review and edit before publishing._",
        ]
        return "\n".join(lines)


def _timeline_from_ledger(ledger: AuditLedger) -> tuple[str, ...]:
    """Turn the audit ledger into a human-readable, chronological timeline.

    The ledger is already append-only and ordered, so the timeline is just a rendering of it —
    which means the postmortem's timeline is *evidence* (it matches the verifiable audit chain),
    not a separate, drift-prone narrative.
    """
    verb = {
        "triage_start": "Triage started",
        "read_tool": "Read signal",
        "retrieve": "Retrieved runbooks/incidents",
        "propose": "Proposed actions",
        "approve": "Action APPROVED",
        "reject": "Action REJECTED",
        "execute": "Action EXECUTED",
        "execute_failed": "Action FAILED",
    }
    out: list[str] = []
    for e in ledger:
        label = verb.get(e.action, e.action)
        detail = ""
        d = e.detail
        if e.action == "read_tool":
            detail = f": {d.get('tool')}({d.get('args', {})})"
        elif e.action == "retrieve":
            detail = f": {', '.join(d.get('sources', [])) or '(none)'}"
        elif e.action in ("approve", "reject", "execute", "execute_failed"):
            detail = f": {d.get('tool')} {d.get('args', {})}"
        elif e.action == "propose":
            detail = f": severity {d.get('severity')} — {d.get('suspected_cause', '')}"
        out.append(f"{e.ts} — {e.actor}: {label}{detail}")
    return tuple(out)


def _model_spans(trace: Trace | None) -> list[Span]:
    """Spans that recorded model usage — used to footnote the trace's shape (not required)."""
    if trace is None:
        return []
    return [s for s in trace.iter_spans() if "gen_ai.usage.input_tokens" in s.attributes]


def draft_postmortem(
    triage: Triage,
    gate: GateReport,
    ledger: AuditLedger,
    *,
    trace: Trace | None = None,
) -> Postmortem:
    """Assemble a :class:`Postmortem` from the triage verdict, the gate decisions, and the trace.

    Nothing here is invented: the severity and suspected cause come from the structured
    :class:`~app.triage.Triage`; the timeline comes from the append-only ledger; the actions-taken
    section comes from the gate's recorded outcomes. The optional ``trace`` lets a live summarizer
    enrich the narrative later, but the draft is complete without it.
    """
    actions_taken: list[str] = []
    for o in gate.outcomes:
        if o.status == "executed":
            actions_taken.append(f"Executed (approved): {o.action.description} → {o.result}")
        elif o.status == "approved":
            actions_taken.append(f"Approved (advisory, no tool): {o.action.description}")
        elif o.status == "rejected":
            actions_taken.append(f"Proposed but REJECTED at the gate: {o.action.description}")
        elif o.status == "failed":
            actions_taken.append(f"Approved but FAILED: {o.action.description} ({o.error})")
    if not gate.outcomes:
        actions_taken.append(
            "No mutating actions were taken (propose-not-act); only read-only investigation."
        )

    follow_ups = [
        "Confirm the mitigation held and metrics returned to SLO.",
        "Update the relevant runbook if the guidance was stale or incomplete.",
        "Add this incident to data/past_incidents.md so the copilot retrieves it next time.",
        "If a mutating verb was repeatedly approved safely, add an eval case before earning autonomy.",
    ]

    cause = triage.suspected_cause.rstrip(".")
    summary = (
        f"{triage.severity.value} on `{triage.service}`. Suspected cause: {cause}. "
        f"The copilot correlated read-only signals, retrieved "
        f"{len(triage.runbook_sources)} relevant runbook/incident source(s), and proposed "
        f"{len(triage.proposed_actions)} action(s) ({len(triage.mutating_actions)} mutating, gated)."
    )

    return Postmortem(
        title=f"{triage.service} incident ({triage.alert_id})",
        severity=triage.severity.value,
        summary=summary,
        timeline=_timeline_from_ledger(ledger),
        root_cause=triage.suspected_cause,
        actions_taken=tuple(actions_taken),
        follow_ups=tuple(follow_ups),
    )
