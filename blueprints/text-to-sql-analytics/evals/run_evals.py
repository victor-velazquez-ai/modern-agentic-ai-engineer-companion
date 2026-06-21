"""Evals for the analytics copilot — composes the **eval-harness** (Ch 22).

The PLAN is blunt about why this matters: *"a plausible-looking wrong number is worse than no
answer."* So the eval doesn't grade the *prose* or whether the SQL "looks right" — it grades the
**result set**. Each golden case carries the exact rows the bundled warehouse must return; a case
passes only if the copilot's rows match. That is the single property that protects trust in a
text-to-SQL system.

Composition (no forking): the candidate under test is the real
:class:`~app.pipeline.AnalyticsCopilot`, and the run/aggregate/threshold machinery is the
eval-harness's :func:`~eval_harness.run` + :class:`~eval_harness.Report`. We add exactly one thing
the harness can't ship generically — a domain grader (:class:`ResultMatch`) that knows result-set
equality and the "this question must be blocked" safety check.

Run it::

    python evals/run_evals.py            # prints the report; exits non-zero if any case fails

Everything is MOCK/offline by default — free and deterministic.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SOLUTION = _HERE.parent
# Make the solution's ``app`` package importable when this file is run as a script.
if str(_SOLUTION) not in sys.path:
    sys.path.insert(0, str(_SOLUTION))

from app import _compose  # noqa: E402,F401  (wires the pattern blueprints onto sys.path)
from app.pipeline import AnalyticsCopilot, CopilotAnswer  # noqa: E402

# Composed pattern blueprint: eval-harness.
from eval_harness import Case, GradeResult, Report, load_jsonl, run  # noqa: E402

GOLDEN = _HERE / "questions_golden.jsonl"
PASS_THRESHOLD = 1.0  # result-set equality is all-or-nothing: an off-by-one number is a failure.


def _normalize_rows(rows) -> list[tuple]:
    """Coerce rows to a comparable shape: ints/floats unified, everything tuple-ized.

    The warehouse may return ``3`` where the golden set wrote ``3`` (or ``3.0``); normalizing both
    to float for numbers makes equality robust to that without weakening the check on values.
    """
    out: list[tuple] = []
    for row in rows:
        cells = []
        for v in row:
            if isinstance(v, bool):
                cells.append(v)
            elif isinstance(v, (int, float)):
                cells.append(float(v))
            else:
                cells.append(v)
        out.append(tuple(cells))
    return out


@dataclass(frozen=True)
class ResultMatch:
    """Grader: did the copilot return the *right rows* — or correctly *block* an unsafe ask?

    Implements the eval-harness ``Grader`` protocol structurally (one ``grade`` method). Two modes,
    chosen by what the golden ``expected`` declares:

    * ``{"rows": [...]}`` — the answer must verify, execute, and return exactly these rows.
    * ``{"blocked": true}`` — the verifier must refuse the query (a safety case).
    """

    def grade(self, expected: dict, actual: dict) -> GradeResult:
        if expected.get("blocked"):
            if actual.get("verified") is False or actual.get("error"):
                return GradeResult.ok("correctly blocked / refused")
            return GradeResult.fail("expected the query to be blocked, but it ran")

        if not actual.get("verified", False):
            reasons = "; ".join(actual.get("verify_reasons", [])) or "unknown"
            return GradeResult.fail(f"query was blocked by verification: {reasons}")
        if actual.get("error"):
            return GradeResult.fail(f"execution error: {actual['error']}")

        exp_rows = _normalize_rows(expected.get("rows", []))
        got_rows = _normalize_rows(actual.get("rows", []))
        if got_rows == exp_rows:
            return GradeResult.ok(f"{len(got_rows)} row(s) matched exactly")
        return GradeResult.fail(
            f"result mismatch: expected {exp_rows!r}, got {got_rows!r}"
        )


def build_candidate(copilot: AnalyticsCopilot):
    """Adapt the copilot to the eval-harness candidate shape: ``question -> graded dict``."""

    def candidate(question: str) -> dict:
        answer: CopilotAnswer = copilot.ask(question, trace=False)
        return answer.to_dict()

    return candidate


def run_evals(path: Path = GOLDEN) -> Report:
    cases: list[Case] = load_jsonl(path)
    copilot = AnalyticsCopilot()
    return run(build_candidate(copilot), cases, ResultMatch(), threshold=PASS_THRESHOLD)


def main() -> int:
    report = run_evals()
    print(report.render())
    # CI gate: any failing case is a non-zero exit (a wrong number must break the build).
    ok = report.pass_rate == 1.0
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
