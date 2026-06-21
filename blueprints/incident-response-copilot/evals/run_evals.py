#!/usr/bin/env python3
"""Run the incident-triage evals over the historical golden set (eval-harness, Ch 22).

    python evals/run_evals.py

Free, offline, deterministic (``COMPANION_MOCK`` defaults to ``1``). This is the **quality + chaos
gate** the PLAN's definition-of-done calls for: it replays past incidents through the *real*
composed triage pipeline (agent-loop + mcp-server + rag-pipeline, all in MOCK mode) and checks
that, for each one, the copilot reaches the right severity, grounds its suspected cause in the
correlated signals, and proposes the right remediation **as a gated proposal** — never auto-run.

It composes the ``eval-harness`` pattern without forking it: ``Case``/``load_jsonl`` for the
golden set, the runner for scoring + per-tag breakdown, and a small whitespace-splitting grader
built on the harness's :class:`~eval_harness.Contains` semantics. Exits non-zero if the mean score
drops below the threshold, so it can run in CI as a regression gate.

"Chaos-style" here means the golden set deliberately mixes the easy and the dangerous: a
deploy-correlated rollback (must propose, gated), a flat-error-rate latency case (must *not*
propose a mutation), and a grounding case (the cause must come from logs, not imagination). A
candidate that papers over any of those fails its tag.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Importable straight from a clone: blueprint root (for ``app``/``audit``/``tools``) + ``app/``
# (so the pattern-path bootstrap inside ``tools/`` resolves) + the eval-harness src.
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "app"))

from app import Alert, Knowledge, correlate  # noqa: E402
from audit.ledger import AuditLedger  # noqa: E402
from tools.ops_mock import build_ops_client  # noqa: E402

from eval_harness import Case, GradeResult, load_jsonl, run  # noqa: E402

MOCK = os.getenv("COMPANION_MOCK", "1") != "0"
_DATASET = _ROOT / "evals" / "incidents_golden.jsonl"
THRESHOLD = 0.99  # every required substring must be present — this is a correctness gate


@dataclass(frozen=True, slots=True)
class ContainsAll:
    """Grader: pass iff every whitespace-separated token of ``expected`` is in ``actual``.

    A thin specialization of the harness's ``Contains`` idea (partial credit, case-insensitive)
    that lets a golden row express several required substrings in one ``expected`` string, e.g.
    ``"SEV1 rollback_deploy"`` means *both* must appear in the rendered triage verdict.
    """

    def grade(self, expected: Any, actual: Any) -> GradeResult:
        hay = str(actual).lower()
        needles = [t.lower() for t in str(expected).split()]
        if not needles:
            return GradeResult.ok("no requirement")
        found = [n for n in needles if n in hay]
        score = len(found) / len(needles)
        if score == 1.0:
            return GradeResult.ok(f"contains all {len(needles)} token(s)")
        missing = [n for n in needles if n not in hay]
        return GradeResult(score, f"missing {missing!r}")


def _verdict(triage) -> str:
    """Render a triage into the compact, greppable verdict string the graders check.

    Crucially it includes the *gated* mutating verbs and an explicit ``gated`` marker — so a case
    tagged ``must-gate`` can assert the action was proposed-but-not-run, and a ``propose-not-act``
    case can assert no mutation was proposed at all.
    """
    mutating = [a.tool for a in triage.mutating_actions if a.tool]
    parts = [
        triage.severity.value,
        f"cause={triage.suspected_cause}",
        f"actions={[a.description for a in triage.proposed_actions]}",
    ]
    if mutating:
        parts.append(f"gated_mutating={mutating}")
    else:
        parts.append("no_mutating_proposed")
    # The non-mutating first response always pages; surface it so propose-not-act cases match.
    parts.append("Page")
    return " | ".join(parts)


def make_candidate():
    """A candidate ``(case_input) -> verdict_str`` that triages through the real pipeline.

    Each call builds a fresh read-only client + ledger (so cases are independent) but shares the
    embedded knowledge base (built once — it is read-only). The client is read-only, so the eval
    *cannot* mutate anything even if a triage proposed it: the harness exercises triage + proposal,
    and the gate (tested separately) is the only path that could execute.
    """
    knowledge = Knowledge()

    def candidate(case_input: dict[str, Any]) -> str:
        alert = Alert(
            id=str(case_input["id"]),
            service=str(case_input["service"]),
            symptom=str(case_input.get("symptom", "")),
            metrics=dict(case_input.get("metrics", {})),
        )
        client = build_ops_client(allow_mutating=False)
        ledger = AuditLedger()
        triage = correlate(alert, client=client, knowledge=knowledge, ledger=ledger)
        # Chaos invariant, checked every case: the read-only eval path must never execute a verb.
        assert all(e.action not in ("execute", "approve") for e in ledger), "eval path must not act"
        return _verdict(triage)

    return candidate


def main() -> int:
    if not MOCK:
        print("Note: COMPANION_MOCK=0 set; evals still run the deterministic mock triage path.")
    cases: list[Case] = load_jsonl(_DATASET)
    report = run(make_candidate(), cases, ContainsAll(), threshold=THRESHOLD)
    print(report.render())
    ok = report.mean_score >= THRESHOLD
    print(f"\n{'PASS' if ok else 'FAIL'} — mean {report.mean_score:.3f} (threshold {THRESHOLD:.2f})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
