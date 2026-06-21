"""The approval gate (Ch 20, 43): the agent *proposes*, a human *approves* each mutating step.

This is the load-bearing safety seam of the whole copilot. ``app/correlate.py`` returns a
:class:`~app.triage.Triage` whose mutating proposals are **labelled and un-run**; nothing in the
correlation path can change production. This module is the *only* place a mutating action can
execute, and it executes one **only** after an approver has said yes to that specific action.

Three properties make the gate trustworthy, all enforced in code rather than documentation:

* **The agent never holds a mutating capability.** Correlation runs against a read-only
  :class:`~mcp_server.SafeMCPClient` (``allow_mutating=False``). The mutating client is
  constructed *here*, lazily, and only to run an action a human already approved — so even a
  fully compromised agent loop cannot reach ``restart_service`` / ``rollback_deploy``.
* **Default-deny.** The default approver (:func:`auto_deny`) rejects everything. In MOCK mode and
  in any non-interactive context the gate therefore *proposes and records but does not act* — the
  ``propose-not-act`` posture is the default you have to consciously override, not the other way
  around.
* **Every decision is evidence.** Approve, reject, and execute each append to the append-only
  audit ledger (Ch 28). "The copilot wanted to roll back and the on-call said no" is exactly the
  line the postmortem needs.

The approver is a tiny seam — ``(ProposedAction) -> bool`` — so the same gate drives a CLI
``y/N`` prompt, a Slack approval button, or a policy that auto-approves only low-risk verbs once
per-action evals (``evals/``) justify it. That progression *is* "earned autonomy".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from . import _bootstrap  # noqa: F401  (wire the composed patterns onto sys.path)

from ..audit.ledger import AuditLedger  # noqa: E402
from ..tools.ops_mock import build_ops_client  # noqa: E402
from .triage import ProposedAction, Triage  # noqa: E402

# An approver decides one mutating action: return True to approve, False to reject.
Approver = Callable[[ProposedAction], bool]


def auto_deny(_action: ProposedAction) -> bool:
    """The safe default approver: reject everything (propose-not-act).

    Used in MOCK mode, in tests, and anywhere there is no human present. Choosing *deny* as the
    default is the entire point of the gate — autonomy must be granted explicitly, never assumed.
    """
    return False


def auto_approve(_action: ProposedAction) -> bool:
    """An approver that accepts every action — for tests/demos of the *execution* path only.

    Never wire this into anything reachable by production. It exists so a test can exercise the
    "approved -> executed -> audited" path deterministically; real deployments pass a human (or a
    narrowly scoped policy) here.
    """
    return True


@dataclass(frozen=True, slots=True)
class ApprovalOutcome:
    """What happened to one mutating proposal at the gate."""

    action: ProposedAction
    approved: bool
    executed: bool
    result: Any = None
    error: str | None = None

    @property
    def status(self) -> str:
        if not self.approved:
            return "rejected"
        if self.error is not None:
            return "failed"
        return "executed" if self.executed else "approved"


@dataclass(slots=True)
class GateReport:
    """The full record of running the gate over a triage's mutating proposals."""

    outcomes: list[ApprovalOutcome] = field(default_factory=list)

    @property
    def approved(self) -> tuple[ApprovalOutcome, ...]:
        return tuple(o for o in self.outcomes if o.approved)

    @property
    def rejected(self) -> tuple[ApprovalOutcome, ...]:
        return tuple(o for o in self.outcomes if not o.approved)

    @property
    def executed(self) -> tuple[ApprovalOutcome, ...]:
        return tuple(o for o in self.outcomes if o.executed)

    def render(self) -> str:
        if not self.outcomes:
            return "No mutating actions were proposed — nothing required approval."
        lines = ["Approval gate:"]
        for o in self.outcomes:
            mark = {"executed": "✓", "approved": "✓", "rejected": "✗", "failed": "!"}[o.status]
            lines.append(f"  {mark} [{o.status}] {o.action.description}")
            if o.error:
                lines.append(f"      error: {o.error}")
        return "\n".join(lines)


def review_and_execute(
    triage: Triage,
    *,
    ledger: AuditLedger,
    approver: Approver = auto_deny,
    approver_id: str = "on-call",
) -> GateReport:
    """Run the human-in-the-loop gate over ``triage``'s mutating proposals.

    For each mutating :class:`~app.triage.ProposedAction`:

    1. ask the ``approver`` (default :func:`auto_deny`);
    2. record an ``approve`` or ``reject`` entry to the audit ledger with the approver's id;
    3. **only if approved**, execute it through a freshly built, mutating-scoped MCP client and
       record an ``execute`` entry with the outcome.

    Non-mutating proposals are not touched here — they carry no authority and need no approval.
    Returns a :class:`GateReport` summarizing every decision. Never raises on a tool failure: a
    failed execution is recorded as such and reported, so one bad action cannot crash the gate.
    """
    report = GateReport()
    mutating = triage.mutating_actions
    if not mutating:
        return report

    # The mutating-scoped client is built lazily and lives only for the duration of this gate
    # call — the agent loop never sees it. Constructed once, reused across approved actions.
    client = None

    for action in mutating:
        approved = bool(approver(action))
        if not approved:
            ledger.append(
                approver_id,
                "reject",
                {"tool": action.tool, "args": action.args, "description": action.description},
            )
            report.outcomes.append(ApprovalOutcome(action=action, approved=False, executed=False))
            continue

        ledger.append(
            approver_id,
            "approve",
            {"tool": action.tool, "args": action.args, "description": action.description},
        )

        # Advice-only proposals (no tool) are "approved" but there is nothing to execute.
        if action.tool is None:
            report.outcomes.append(ApprovalOutcome(action=action, approved=True, executed=False))
            continue

        if client is None:
            client = build_ops_client(allow_mutating=True)

        try:
            result = client.call(action.tool, action.args)
            ledger.append(
                approver_id,
                "execute",
                {"tool": action.tool, "args": action.args, "result": result},
            )
            report.outcomes.append(
                ApprovalOutcome(action=action, approved=True, executed=True, result=result)
            )
        except Exception as exc:  # noqa: BLE001 — a failed action is recorded, not raised
            ledger.append(
                approver_id,
                "execute_failed",
                {"tool": action.tool, "args": action.args, "error": str(exc)},
            )
            report.outcomes.append(
                ApprovalOutcome(
                    action=action, approved=True, executed=False, error=f"{type(exc).__name__}: {exc}"
                )
            )

    return report
