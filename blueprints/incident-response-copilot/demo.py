#!/usr/bin/env python3
"""Runnable demo — alert → triage → runbook → gated remediation → postmortem, in MOCK mode.

    python demo.py

Runs **free, offline, and deterministically** (``COMPANION_MOCK`` defaults to ``1``; no keys, no
network, no API spend). It drives the whole incident-response copilot end to end by *composing*
five pattern blueprints — none of them forked:

* **agent-loop** correlates read-only signals (metrics, logs, deploys);
* **mcp-server** serves those signals as least-privilege, schema-validated tools;
* **rag-pipeline** retrieves the matching runbook + a similar past incident;
* **eval-harness** (see ``evals/``) scores the triage against a golden set;
* **observability-stack** records the incident trace that the postmortem reads from, and seams
  into the append-only **audit ledger** (Ch 28).

The autonomy dial is tight on purpose: the agent only ever *proposes* mutating actions. This demo
runs the human-in-the-loop gate twice — once with the **safe default (deny)**, so nothing touches
"production", and once with an explicit approver, to show the approved → executed → audited path —
then drafts a postmortem from the trace + ledger. Set ``COMPANION_MOCK=0`` and inject an
``llm-gateway`` model port to go live; the composition does not change.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# The composed observability console exporter renders the trace tree with a few non-ASCII glyphs
# (e.g. '·'). On a Windows console defaulting to cp1252 that would raise UnicodeEncodeError, so we
# switch this process's stdout/stderr to UTF-8. Best-effort: older streams may lack reconfigure().
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
        pass

# Make this hyphenated blueprint importable straight from a clone (before any `pip install -e`).
# ``_loader.bootstrap_package`` registers the directory as the package ``incident_response_copilot``
# so the solution's relative imports (``from ..audit ...``) resolve, and puts the composed pattern
# blueprints on the path via ``app/_bootstrap.py`` — none of them are forked.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import bootstrap_package  # noqa: E402

bootstrap_package()

from incident_response_copilot.app import (  # noqa: E402  (after the package bootstrap)
    Alert,
    Knowledge,
    auto_approve,
    auto_deny,
    correlate,
    draft_postmortem,
    review_and_execute,
)
from incident_response_copilot.audit.ledger import AuditLedger  # noqa: E402
from incident_response_copilot.tools.ops_mock import build_ops_client  # noqa: E402

from observability_stack import ConsoleExporter, Tracer  # noqa: E402

MOCK = os.getenv("COMPANION_MOCK", "1") != "0"

# The alert that pages us: checkout is on fire. The mock ops fixture (tools/ops_mock.py) has
# matching metrics/logs/deploys, so the correlation is real even though it spends nothing.
ALERT = Alert(
    id="ALERT-9001",
    service="checkout",
    symptom="elevated 5xx error rate, customers seeing failed orders",
    metrics={"error_rate": 0.42, "p99_latency_ms": 5200},
)


def _print_triage(triage) -> None:
    print(f"\nTRIAGE  [{triage.alert_id}]  service={triage.service}")
    print(f"  severity        : {triage.severity.value}")
    print(f"  suspected cause : {triage.suspected_cause}")
    sources = list(dict.fromkeys(triage.runbook_sources))  # de-dup, preserve order, for display
    print(f"  runbook sources : {', '.join(sources) or '(none)'}")
    print("  proposed actions:")
    for a in triage.proposed_actions:
        gate = "MUTATING (gated)" if a.mutating else "non-mutating"
        tool = f"  via {a.tool}{a.args}" if a.tool else ""
        print(f"    - [{gate}] {a.description}{tool}")


def main() -> int:
    if not MOCK:
        raise SystemExit(
            "COMPANION_MOCK=0 set, but this demo ships only the mock path. Inject an "
            "llm-gateway-backed ModelPort into correlate() to run live (see README → Live path)."
        )

    print(f"MOCK={'1' if MOCK else '0'}  |  composing: agent-loop + rag-pipeline + mcp-server + "
          "observability-stack + eval-harness")
    print(f"\nPAGE: {ALERT.describe()}")

    # The composed substrate: a read-only ops client (the agent NEVER gets mutating verbs), the
    # runbook/incident retriever, an append-only audit ledger, and one tracer for the incident.
    read_client = build_ops_client(allow_mutating=False)
    knowledge = Knowledge()
    ledger = AuditLedger()
    tracer = Tracer()

    print(f"\nknowledge base: {len(knowledge)} chunks over runbooks + past incidents")
    print(f"agent tool surface (read-only, allow-listed): {sorted(read_client.allowed)}")

    # 1) Correlate: agent-loop over read tools + RAG → a structured, gated Triage.
    triage = correlate(ALERT, client=read_client, knowledge=knowledge, ledger=ledger, tracer=tracer)
    _print_triage(triage)

    # 2) Approval gate, run twice to show both postures.
    #    (a) Safe default: deny — propose-not-act. Nothing touches "production".
    print("\n--- Approval gate (default policy: DENY / propose-not-act) ---")
    denied = review_and_execute(triage, ledger=ledger, approver=auto_deny)
    print(denied.render())

    #    (b) Explicit approval of the rollback (the deploy correlated with the error onset),
    #        showing the approved → executed → audited path. A real gate prompts a human here.
    def approve_rollbacks(action) -> bool:
        return action.tool == "rollback_deploy"

    print("\n--- Approval gate (on-call APPROVES the correlated rollback) ---")
    approved = review_and_execute(triage, ledger=ledger, approver=approve_rollbacks)
    print(approved.render())

    # 3) Postmortem: drafted from the incident trace + the append-only ledger, not from memory.
    print("\n--- Postmortem draft (from trace + audit ledger) ---")
    pm = draft_postmortem(triage, approved, ledger, trace=tracer.trace)
    print(pm.to_markdown())

    # 4) The audit ledger is append-only and tamper-evident; show it verifies.
    print("\n--- Audit ledger ---")
    print(f"entries: {len(ledger)}  |  chain verifies: {ledger.verify()}")

    # 5) The incident trace (what the postmortem read from), as a tree + cost roll-up.
    print("\n--- Incident trace ---")
    ConsoleExporter().export(tracer.trace)

    # A blueprint demo is also a smoke test: assert the happy path actually happened.
    assert triage.severity.value == "SEV1", triage.severity
    assert any(a.tool == "rollback_deploy" for a in triage.mutating_actions), "expected a rollback proposal"
    assert denied.executed == (), "default-deny must execute nothing"
    assert any(o.executed for o in approved.executed), "approved rollback should have executed"
    assert ledger.verify(), "audit ledger must verify"
    # auto_approve is exported for tests of the full execution path; reference it so it stays wired.
    assert callable(auto_approve)
    print("\nOK — alert triaged, remediation gated + (selectively) executed, postmortem drafted, "
          "audit chain intact — with no API spend.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
