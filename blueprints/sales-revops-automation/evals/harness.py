"""Score the call->CRM extraction against the golden set (composes ``eval-harness``).

This is the PLAN's "extraction-accuracy eval set" wired to the **``eval-harness``** pattern
blueprint. It does three things, all offline and free:

1. **A candidate** (:func:`extract_candidate`) that runs the *real* :func:`workflow.call_to_crm.process_call`
   for a case's call id and returns the fields that were actually **written** to the CRM (the
   ``applied`` map). Grading the written fields — not the raw extraction — is deliberate: the
   forecast only sees what survives the conservative-write gate, so that is what the eval must hold.
2. **A field-level grader** (:class:`FieldsMatch`) that scores the written fields against the
   expected map with **partial credit** (fraction of expected fields present and equal), and —
   critically — **penalises extra written fields** the case didn't expect. That second half is the
   conservative-write guardrail: writing a hedged amount into the forecast is a *failure*, even if
   every expected field is also present.
3. **A guardrail eval** (:func:`guardrail_report`) for the wrong-recipient check — a draft addressed
   to a foreign domain must be HELD. Mis-sending is the most expensive failure mode, so it gets its
   own gate alongside extraction accuracy (Ch 22/41).

Run ``python -m evals.harness`` to print both reports. The ``eval-harness`` runner, ``Report``, and
``render`` are imported, never forked; only the candidate and grader are domain-specific.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from revops.compose import ensure_on_path

ensure_on_path()

from eval_harness import Case, GradeResult, Report, load_jsonl, run  # noqa: E402

from workflow.call_to_crm import process_call  # noqa: E402
from workflow.draft_outreach import recipient_is_valid  # noqa: E402

_HERE = Path(__file__).resolve().parent
_GOLDEN = _HERE / "extraction_golden.jsonl"
_CALLS_DIR = _HERE.parent / "data" / "calls"


def _load_call(call_stem: str) -> dict[str, Any]:
    """Load one sample call record by its file stem (the case ``input``)."""
    return json.loads((_CALLS_DIR / f"{call_stem}.json").read_text(encoding="utf-8"))


def extract_candidate(call_stem: str) -> dict[str, Any]:
    """The system under test: run the workflow and return the fields it WROTE to the CRM.

    A case's ``input`` is a call-file stem (e.g. ``"globex-002-proposal"``). We run the real
    extraction + conservative-write path and return ``applied`` — what actually landed in the CRM.
    """
    call = _load_call(call_stem)
    result = process_call(call)
    return result.applied


@dataclass(frozen=True, slots=True)
class FieldsMatch:
    """Field-level grader: partial credit for correct fields, penalty for surprises.

    Score = (correct expected fields) / (expected fields + unexpected extra fields). So:

    * every expected field present and equal, with no extras -> 1.0;
    * a missing or wrong field -> proportional loss (you can see *which* slipped);
    * an **extra** field the case didn't expect (e.g. a hedged amount that should have been
      withheld) -> also lowers the score, because over-writing the forecast is a real failure.

    Never raises — a non-dict candidate output scores 0 with a rationale.
    """

    def grade(self, expected: Any, actual: Any) -> GradeResult:
        if not isinstance(expected, dict):
            return GradeResult.fail(f"expected must be an object, got {type(expected).__name__}")
        if not isinstance(actual, dict):
            return GradeResult.fail(f"candidate did not return an object: {actual!r}")

        correct = [k for k, v in expected.items() if k in actual and actual[k] == v]
        wrong = [k for k in expected if k in actual and actual[k] != expected[k]]
        missing = [k for k in expected if k not in actual]
        extra = [k for k in actual if k not in expected]

        denom = len(expected) + len(extra)
        score = (len(correct) / denom) if denom else 1.0

        if score == 1.0:
            return GradeResult.ok(f"all {len(expected)} field(s) written correctly, no extras")
        problems = []
        if missing:
            problems.append(f"missing {missing}")
        if wrong:
            problems.append(f"wrong {wrong}")
        if extra:
            problems.append(f"unexpected (should withhold) {extra}")
        return GradeResult(score, "; ".join(problems) or "partial match")


def load_cases() -> list[Case]:
    """Load the extraction golden set."""
    return load_jsonl(_GOLDEN)


def evaluate(*, threshold: float = 0.99) -> Report:
    """Run the extraction golden set through the ``eval-harness`` runner and return the report.

    The threshold is intentionally strict (0.99): for a structured-extraction gate, a field is
    right or it isn't, and a 'mostly right' write into a forecast is still a defect to investigate.
    """
    cases = load_cases()
    return run(extract_candidate, cases, FieldsMatch(), threshold=threshold)


# --- the wrong-recipient guardrail eval (Ch 22/41) ---------------------------------------------


@dataclass(frozen=True, slots=True)
class GuardrailCase:
    """One recipient-guardrail check: an address and whether it should be ALLOWED for the account."""

    name: str
    to_email: str
    should_allow: bool


def _guardrail_cases(account: dict[str, Any]) -> list[GuardrailCase]:
    """A few recipient checks against a real account snapshot (the primary contact + attackers)."""
    contact = str(account.get("primary_contact", {}).get("email", ""))
    domain = str(account.get("domain", ""))
    return [
        GuardrailCase("known-contact", contact, True),
        GuardrailCase("same-domain", f"someone.else@{domain}", True),
        GuardrailCase("foreign-domain", "buyer@competitor.com", False),
        GuardrailCase("personal-domain", "priya.personal@gmail.com", False),
        GuardrailCase("not-an-email", "priya", False),
    ]


def guardrail_report() -> tuple[int, int, list[str]]:
    """Check the wrong-recipient guardrail on a real account; return ``(passed, total, failures)``.

    Verifies that :func:`workflow.draft_outreach.recipient_is_valid` allows the account's own
    contacts/domain and HOLDS anything else — the gate that prevents a draft from being addressed
    to the wrong company.
    """
    account = _load_call("acme-001-discovery")  # reuse the account snapshot fields we need
    # The call record carries only account_id; pull the full account from the CRM store seed.
    from tools.crm_mock import CRMStore

    snapshot = CRMStore().get_account(str(account["account_id"]))
    cases = _guardrail_cases(snapshot)

    passed = 0
    failures: list[str] = []
    for c in cases:
        ok, reason = recipient_is_valid(snapshot, c.to_email)
        if ok == c.should_allow:
            passed += 1
        else:
            verdict = "ALLOWED" if ok else "HELD"
            failures.append(f"{c.name}: {c.to_email!r} was {verdict} (expected the opposite) — {reason}")
    return passed, len(cases), failures


def main() -> int:
    """Print both reports; exit non-zero if extraction regresses or a guardrail check fails."""
    os.environ.setdefault("COMPANION_MOCK", "1")
    for stream_name in ("stdout", "stderr"):
        stream = getattr(__import__("sys"), stream_name)
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # pragma: no cover
            pass

    report = evaluate()
    print(report.render())

    g_passed, g_total, g_failures = guardrail_report()
    print()
    print("Wrong-recipient guardrail")
    print("-" * 40)
    print(f"checks    : {g_passed}/{g_total} passed")
    for f in g_failures:
        print(f"  x {f}")

    ok = report.pass_rate == 1.0 and g_passed == g_total
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
