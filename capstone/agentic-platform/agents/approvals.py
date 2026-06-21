"""Human-in-the-loop approval gates (Ch 20) — risk-tier table → pause → resume.

This is the wiring that turns a tool's declared :class:`~agents.tools.schemas.RiskTier` into a
*decision* the agent loop honors before it acts: **auto-approve**, **deny**, or **hold for a
human**. It is the missing safety primitive between "the model wants to send this email" and "the
email is sent": a structural gate, not a polite request in the system prompt. (The Ch 20 lesson:
prompts ask; structure enforces.)

The design has three moving parts, each small and testable:

* :class:`ApprovalPolicy` — the rule. "Gate everything ``EXTERNAL`` and above" is the default; you
  can also pin specific tools to always/never gate. Given a tool's tier, it returns a
  :class:`Decision`.
* :class:`ApprovalRequest` / :class:`ApprovalResolution` — the *paused* state. When a call is
  held, the loop stops with a request the caller (API/UI) surfaces to a human; the human's
  decision comes back as a resolution and the run resumes. This is why the transcript is
  snapshot-able: a hold is just a run you can pickle and continue later.
* :class:`ApprovalStore` — where pending requests wait. The in-memory store ships here for tests
  and the local stack; the real platform backs it with the DB (``app/``) so a hold survives a
  process restart and a different worker can resume it.

Nothing here calls a model or does I/O beyond the store, so the policy is pure and the gate is the
same whether the loop runs in ``raw/``, ``graph/``, or behind a Celery worker.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from .tools.messages import ToolCall, ToolResult
from .tools.schemas import RiskTier, ToolRegistry


class Decision(str, Enum):
    """What the policy decided about a single tool call."""

    ALLOW = "allow"      # run it now, unattended
    HOLD = "hold"        # pause: a human must approve before it runs
    DENY = "deny"        # never run it (a hard block, e.g. a forbidden tool)


@dataclass(frozen=True, slots=True)
class ApprovalPolicy:
    """The rule that maps a tool's risk tier to a :class:`Decision`.

    Defaults to the platform's posture: **gate ``EXTERNAL`` and above** (anything that leaves the
    boundary or is privileged), auto-approve ``READ``/``WRITE``. Override per tool with
    ``always_gate`` (force a hold even if its tier is low) and ``never_gate`` (trust a specific
    tool regardless of tier — use sparingly, and only for tools you have reviewed).

    A blocked set (``deny``) lets a tenant hard-disable a tool: the model may *ask* for it, but the
    gate returns ``DENY`` and the call never runs.
    """

    gate_at_or_above: RiskTier = RiskTier.EXTERNAL
    always_gate: frozenset[str] = field(default_factory=frozenset)
    never_gate: frozenset[str] = field(default_factory=frozenset)
    deny: frozenset[str] = field(default_factory=frozenset)

    def decide(self, *, tool_name: str, risk: RiskTier) -> Decision:
        """Return the decision for a call to ``tool_name`` declared at ``risk``."""
        if tool_name in self.deny:
            return Decision.DENY
        if tool_name in self.never_gate:
            return Decision.ALLOW
        if tool_name in self.always_gate:
            return Decision.HOLD
        return Decision.HOLD if risk >= self.gate_at_or_above else Decision.ALLOW

    @classmethod
    def strict(cls) -> "ApprovalPolicy":
        """A cautious policy: gate ``WRITE`` and above (every side effect needs a human)."""
        return cls(gate_at_or_above=RiskTier.WRITE)

    @classmethod
    def permissive(cls) -> "ApprovalPolicy":
        """A trusting policy: gate only ``ADMIN`` (privileged/irreversible) calls."""
        return cls(gate_at_or_above=RiskTier.ADMIN)


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """A held tool call awaiting a human decision — the serializable 'paused' unit.

    Carries everything a reviewer needs to decide: which tool, with what arguments, why it was
    held (the tier), and a stable ``id`` to resolve against. ``run_id`` ties it back to the agent
    run so the API/UI can route the approval card to the right conversation.
    """

    id: str
    run_id: str
    call: ToolCall
    risk: RiskTier
    reason: str
    created_at: str

    @classmethod
    def for_call(cls, *, run_id: str, call: ToolCall, risk: RiskTier) -> "ApprovalRequest":
        return cls(
            id=f"apr_{uuid.uuid4().hex[:12]}",
            run_id=run_id,
            call=call,
            risk=risk,
            reason=f"tool {call.name!r} is risk tier {risk.value!r}; human approval required",
            created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )


@dataclass(frozen=True, slots=True)
class ApprovalResolution:
    """A human's verdict on an :class:`ApprovalRequest`."""

    request_id: str
    approved: bool
    decided_by: str = "unknown"
    note: str = ""
    decided_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    )


class ApprovalStore:
    """Where pending requests wait between a hold and a human's decision (in-memory default).

    The in-memory implementation is fine for tests and the local stack. The production platform
    swaps in a DB-backed store (``app/db``) so a hold survives a restart and any worker can resume
    it — same surface, different backend, which is exactly the seam the modular monolith preserves.
    """

    def __init__(self) -> None:
        self._pending: dict[str, ApprovalRequest] = {}
        self._resolved: dict[str, ApprovalResolution] = {}

    def put(self, request: ApprovalRequest) -> ApprovalRequest:
        self._pending[request.id] = request
        return request

    def pending(self) -> list[ApprovalRequest]:
        return list(self._pending.values())

    def get(self, request_id: str) -> ApprovalRequest | None:
        return self._pending.get(request_id)

    def resolve(self, resolution: ApprovalResolution) -> ApprovalRequest:
        """Record a human's decision and remove the request from the pending set.

        Raises :class:`KeyError` if the request is unknown (resolving twice, or a bad id) — a
        caller should treat that as "already decided / not found", never silently swallow it.
        """
        req = self._pending.pop(resolution.request_id, None)
        if req is None:
            raise KeyError(f"no pending approval request {resolution.request_id!r}")
        self._resolved[resolution.request_id] = resolution
        return req

    def resolution_for(self, request_id: str) -> ApprovalResolution | None:
        return self._resolved.get(request_id)


# A gate function: given a run id and a tool call, return how to proceed. The loop calls this
# before executing each call. Returning a request (rather than raising) keeps the loop in charge of
# *how* to pause (snapshot + stop), which differs per variant.
GateFn = Callable[[str, ToolCall], "GateOutcome"]


@dataclass(frozen=True, slots=True)
class GateOutcome:
    """The gate's verdict for one call: allow it, hold it (with a request), or deny it.

    Exactly one of ``request``/``denied_result`` is set when the decision is not ``ALLOW``; on
    ``ALLOW`` both are ``None`` and the loop runs the call normally.
    """

    decision: Decision
    request: ApprovalRequest | None = None
    denied_result: ToolResult | None = None


@dataclass
class ApprovalGate:
    """Binds a :class:`ApprovalPolicy`, a :class:`ToolRegistry`, and a store into a callable gate.

    The agent loop calls :meth:`check` before each tool call. The gate looks up the tool's declared
    risk, asks the policy, and:

    * ``ALLOW`` → returns an allow outcome; the loop executes the call;
    * ``HOLD``  → records an :class:`ApprovalRequest` in the store and returns it; the loop
      snapshots its transcript and stops with a "needs approval" reason for the API/UI to surface;
    * ``DENY``  → returns a *denied* :class:`ToolResult` the loop feeds back to the model (so the
      model learns the tool is off-limits and can try another path), no human involved.

    :meth:`apply` is the resume side: given a resolution, it either returns the call to execute
    (approved) or a denied result to thread back (rejected).
    """

    policy: ApprovalPolicy
    tools: ToolRegistry
    store: ApprovalStore = field(default_factory=ApprovalStore)

    def check(self, run_id: str, call: ToolCall) -> GateOutcome:
        """Decide what to do with one pending tool call."""
        risk = self.tools.risk_of(call.name)
        decision = self.policy.decide(tool_name=call.name, risk=risk)
        if decision is Decision.ALLOW:
            return GateOutcome(Decision.ALLOW)
        if decision is Decision.DENY:
            return GateOutcome(
                Decision.DENY,
                denied_result=ToolResult(
                    call_id=call.id,
                    name=call.name,
                    content=(
                        f"tool {call.name!r} is denied by policy and was not run; "
                        "choose a different approach."
                    ),
                    ok=False,
                ),
            )
        request = self.store.put(ApprovalRequest.for_call(run_id=run_id, call=call, risk=risk))
        return GateOutcome(Decision.HOLD, request=request)

    def apply(self, resolution: ApprovalResolution) -> tuple[ToolCall | None, ToolResult | None]:
        """Resolve a held request. Returns ``(call_to_run, None)`` if approved, else ``(None, result)``.

        On approval the original :class:`ToolCall` is returned for the loop to execute on resume.
        On rejection a denied :class:`ToolResult` is returned to thread back to the model — the run
        continues, having been told a human declined the action.
        """
        request = self.store.resolve(resolution)
        if resolution.approved:
            return request.call, None
        note = f" ({resolution.note})" if resolution.note else ""
        return None, ToolResult(
            call_id=request.call.id,
            name=request.call.name,
            content=f"a human declined this action{note}; do not retry it. Propose an alternative.",
            ok=False,
        )
