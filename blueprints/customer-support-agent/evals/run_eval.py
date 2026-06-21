"""Score the support agent against the golden set and gate on resolution (Ch 22).

This is the quality gate the PLAN demands. It composes the ``eval-harness`` pattern blueprint:

* :func:`eval_harness.load_jsonl` loads ``tickets_golden.jsonl`` (one ticket per row; ``expected``
  is the action the agent *should* take, plus, for answer-only cases, the source it must cite).
* a small **resolution grader** (defined here, satisfying the ``Grader`` protocol) scores each
  case on whether the agent took the right action — and, for a ``RESOLVE``, whether it cited the
  expected help-center doc. **Resolution, not deflection**: a case tagged ``must-escalate`` only
  passes if the agent actually escalated.
* :func:`eval_harness.run` aggregates per-tag (so a regression that only hits ``must-escalate`` is
  visible), and :func:`eval_harness.gate` fails the build (non-zero exit) if scores drop past a
  tolerance below the committed baseline.

The candidate is the *real* :class:`~app.support_agent.SupportAgent` — so this eval exercises the
whole composed solution (RAG + tools + policy), exactly as it runs in the demo. Everything is
free and deterministic in MOCK mode.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Put this solution's root on the path so ``app`` / ``data`` / ``tools`` import as packages,
# whether this file is imported (from ``demo.py``) or run directly (``python evals/run_eval.py``).
_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

# Wire the sibling pattern blueprints onto the path before importing them.
from app import _paths  # noqa: E402,F401

from eval_harness import GradeResult, Report, gate, load_jsonl, run  # noqa: E402

from app.decision import Decision  # noqa: E402
from app.support_agent import SupportAgent  # noqa: E402

GOLDEN_PATH = _HERE / "tickets_golden.jsonl"
BASELINE_PATH = _HERE / "baseline.json"

# Resolution is the bar: take the right action, and cite the right source when answering.
PASS_THRESHOLD = 0.5
GATE_TOLERANCE = 0.02


@dataclass(frozen=True)
class ResolutionGrader:
    """Grade a :class:`Decision` (as a dict) against a case's expected resolution.

    ``expected`` shape in the golden set::

        {"action": "resolve|act|escalate",
         "expect_source": "refund-policy",     # optional: a doc_id the citations must include
         "expect_tool": "issue_refund"}        # optional: the scoped tool an ACT must have used

    Scoring (resolution, not deflection):

    * wrong **action** → 0.0 (the cardinal sin: answering when it should escalate, or vice versa);
    * right action, but a required **source**/**tool** is missing → 0.5 (acted correctly but not
      grounded/scoped as required — a partial, surfaced in the rationale);
    * right action *and* grounding/scoping → 1.0.
    """

    def grade(self, expected: Any, actual: Any) -> GradeResult:
        if not isinstance(expected, dict):
            return GradeResult.fail("malformed expected (not an object)")
        if not isinstance(actual, dict):
            return GradeResult.fail(f"candidate did not return a decision dict: {actual!r}")

        want_action = str(expected.get("action", "")).lower()
        got_action = str(actual.get("action", "")).lower()
        if want_action != got_action:
            return GradeResult.fail(f"action {got_action!r} != expected {want_action!r}")

        # Right action. Now check grounding/scoping requirements for full credit.
        if want_action == "resolve":
            want_source = expected.get("expect_source")
            cited = {c.get("doc_id") for c in actual.get("citations", [])}
            if not cited:
                return GradeResult(0.5, f"resolved but uncited (a RESOLVE must cite a source)")
            if want_source and want_source not in cited:
                return GradeResult(0.5, f"resolved & cited {sorted(cited)} but not {want_source!r}")
            return GradeResult.ok(f"resolved, cited {sorted(cited)}")

        if want_action == "act":
            want_tool = expected.get("expect_tool")
            got_tool = actual.get("tool")
            if want_tool and got_tool != want_tool:
                return GradeResult(0.5, f"acted via {got_tool!r}, expected tool {want_tool!r}")
            return GradeResult.ok(f"acted via scoped tool {got_tool!r}")

        # escalate
        return GradeResult.ok(f"escalated: {actual.get('escalation_reason', '')[:60]}")


def _candidate(agent: SupportAgent):
    """Adapt the agent into an eval candidate: ``ticket-text -> decision dict``."""

    def candidate(ticket: Any) -> dict[str, Any]:
        decision: Decision = agent.handle(str(ticket))
        return decision.to_dict()

    return candidate


def evaluate(agent: SupportAgent) -> Report:
    """Run the agent over the golden set and return the aggregated :class:`Report`."""
    cases = load_jsonl(GOLDEN_PATH)
    return run(_candidate(agent), cases, ResolutionGrader(), threshold=PASS_THRESHOLD)


def _force_utf8_console() -> None:
    """Make the ✓/✗ glyphs in the gate report print on any console (incl. Windows cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
            pass


def main(*, agent: SupportAgent | None = None) -> int:
    """Score + gate. Returns ``0`` on pass, ``1`` on regression (CI-usable exit code)."""
    _force_utf8_console()
    if agent is None:
        # Build the same composed agent the demo uses.
        from data import load_help_center
        from tools.billing_mock import build_support_client

        client = build_support_client()
        agent = SupportAgent.from_help_center(
            load_help_center(),
            tool_caller=lambda name, args: client.call(name, args),
        )

    report = evaluate(agent)
    print(report.render())

    if not BASELINE_PATH.exists():
        # First run: write the baseline so subsequent runs can gate against it.
        from eval_harness import save_baseline

        save_baseline(report, BASELINE_PATH)
        print(f"\nNo baseline yet — wrote {BASELINE_PATH.name}. Re-run to gate against it.")
        return 0

    from eval_harness import load_baseline

    result = gate(report, load_baseline(BASELINE_PATH), tolerance=GATE_TOLERANCE)
    print()
    print(result.render())
    return result.exit_code


if __name__ == "__main__":
    import os

    os.environ.setdefault("COMPANION_MOCK", "1")
    raise SystemExit(main())
