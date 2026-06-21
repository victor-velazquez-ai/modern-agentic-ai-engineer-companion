"""Structured triage output (Ch 15): severity, suspected cause, and *proposed* actions.

The first thing a responder needs is not prose — it is **structure**: how bad is this, what is the
likely cause, and what are the candidate next steps. Ch 15 ("structured outputs") is exactly this
discipline: force the model (or, in MOCK mode, a deterministic stand-in) to emit a typed object
you can validate, route, and audit, instead of a paragraph you have to re-parse under pressure.

Two key shapes:

* :class:`Alert` — the incoming signal (service, symptom, metric snapshot). What a pager sends.
* :class:`Triage` — the structured verdict. Its ``proposed_actions`` is the heart of the
  *propose-not-act* posture: each candidate remediation is labelled ``mutating`` or not, and a
  mutating action carries **no authority** here — it is a *proposal* that the approval gate
  (``app/approve.py``) must clear before anything touches production.

The MOCK triage is rule-based and deterministic so the demo and the eval set reproduce exactly.
On the live path you would swap :func:`triage_alert`'s body for a gateway-backed structured call
(the ``llm-gateway`` blueprint) returning the *same* :class:`Triage` schema — nothing downstream
changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    """How bad — SEV1 (worst) … SEV4. Drives paging, comms, and how tight the autonomy dial is."""

    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"
    SEV4 = "SEV4"


@dataclass(frozen=True, slots=True)
class Alert:
    """An incoming alert — the trigger for triage.

    ``metrics`` is a free-form snapshot (error_rate, p99_latency_ms, …) the pager attached; it is
    optional because triage also *pulls* fresh metrics via the ops tools during correlation.
    """

    id: str
    service: str
    symptom: str
    metrics: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> str:
        """One-line human framing used to seed retrieval and the agent loop."""
        m = ", ".join(f"{k}={v}" for k, v in self.metrics.items())
        tail = f" ({m})" if m else ""
        return f"[{self.id}] {self.service}: {self.symptom}{tail}"


@dataclass(frozen=True, slots=True)
class ProposedAction:
    """One candidate remediation step — a *proposal*, never an executed action.

    ``mutating`` is the load-bearing field: ``True`` means this step changes production and is
    therefore gated behind human approval. ``tool``/``args`` name the scoped ops tool that would
    carry it out *if approved* (see ``tools/ops_mock.py``); a ``None`` tool is advice for a human
    to perform manually.
    """

    description: str
    mutating: bool
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class Triage:
    """The structured triage verdict for one alert."""

    alert_id: str
    service: str
    severity: Severity
    suspected_cause: str
    proposed_actions: tuple[ProposedAction, ...] = field(default_factory=tuple)
    runbook_sources: tuple[str, ...] = field(default_factory=tuple)

    @property
    def mutating_actions(self) -> tuple[ProposedAction, ...]:
        """The subset of proposals that require approval before they can run."""
        return tuple(a for a in self.proposed_actions if a.mutating)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "service": self.service,
            "severity": self.severity.value,
            "suspected_cause": self.suspected_cause,
            "proposed_actions": [
                {
                    "description": a.description,
                    "mutating": a.mutating,
                    "tool": a.tool,
                    "args": a.args,
                    "rationale": a.rationale,
                }
                for a in self.proposed_actions
            ],
            "runbook_sources": list(self.runbook_sources),
        }


def severity_from_metrics(metrics: dict[str, Any]) -> Severity:
    """Map a metric snapshot to a severity (deterministic; the MOCK triage policy).

    Error rate dominates (a customer-facing failure is worse than slowness); latency is the
    tie-breaker. The thresholds are intentionally explicit so they are reviewable and testable —
    a real deployment would tune them per service SLO.
    """
    err = float(metrics.get("error_rate", 0.0))
    p99 = float(metrics.get("p99_latency_ms", 0.0))
    if err >= 0.2:
        return Severity.SEV1
    if err >= 0.05 or p99 >= 2000:
        return Severity.SEV2
    if err >= 0.01 or p99 >= 800:
        return Severity.SEV3
    return Severity.SEV4
