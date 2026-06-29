"""The eval runner + CI quality gate (Ch 22).

This is the file Appendix C names: ``run_evals.py`` — load a golden set, score a candidate
over it, aggregate per-tag, and **gate** the build against a committed baseline. It is both an
importable API and a CLI a CI step invokes.

The two halves:

* **Runner.** A *candidate* is the thing under test: ``(input) -> output``. Usually it's an
  agent or a prompt, but it's just a callable, so a fixed string, a stub, or a recorded
  transcript all work. :func:`run_suite` feeds each case's ``input`` to the candidate, grades
  the output, and rolls per-case scores into a :class:`Report` with an overall mean **and a
  per-tag breakdown** — because a single accuracy number hides the regression that only hit
  ``must-refuse`` cases.
* **Gate.** :func:`gate` compares a fresh report to a ``baseline.json`` (the scores you accept
  today). If the overall mean — or any per-tag score — drops more than ``tolerance`` below
  baseline, the gate **fails the build** with a non-zero exit code and a readable diff. Quality
  becomes a red check, not a code-review vibe.

The exit-code contract the CLI honours (and tests/CI read): ``0`` ok / ``1`` regression /
``2`` usage error. ``tolerance`` exists because LLM-judge scores have run-to-run noise; set it
a few points above your judge's observed variance so the gate flags real drops, not jitter.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .dataset import Case, load_jsonl
from .graders import (
    Contains,
    ExactMatch,
    GradeResult,
    Grader,
    JSONSchemaMatch,
    LLMJudge,
    RegexMatch,
)

# The system under test: given a case's input, produce an output to grade.
Candidate = Callable[[Any], Any]
# Either one grader for all cases, or a function that picks a grader per case.
GraderSelector = Grader | Callable[[Case], Grader]

DEFAULT_PASS_THRESHOLD = 0.5
DEFAULT_TOLERANCE = 0.02

EXIT_OK = 0
EXIT_REGRESSION = 1
EXIT_USAGE = 2


# ======================================================================================
# Report shapes
# ======================================================================================


@dataclass(frozen=True, slots=True)
class CaseResult:
    """The graded outcome for a single case."""

    case_id: str
    tags: tuple[str, ...]
    score: float
    passed: bool
    rationale: str
    output: Any = field(default=None, repr=False)

    @property
    def failed(self) -> bool:
        return not self.passed


@dataclass(frozen=True, slots=True)
class TagStat:
    """Aggregate score for one tag segment."""

    tag: str
    count: int
    mean_score: float
    passed: int

    @property
    def pass_rate(self) -> float:
        return self.passed / self.count if self.count else 0.0


@dataclass(frozen=True, slots=True)
class Report:
    """The aggregate result of a run: overall + per-case + per-tag."""

    results: tuple[CaseResult, ...]
    threshold: float = DEFAULT_PASS_THRESHOLD

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def mean_score(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.score for r in self.results) / len(self.results)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def failures(self) -> tuple[CaseResult, ...]:
        return tuple(r for r in self.results if r.failed)

    def by_tag(self) -> dict[str, TagStat]:
        """Mean score and pass count per tag (a case contributes to each of its tags)."""

        buckets: dict[str, list[CaseResult]] = {}
        for r in self.results:
            for tag in r.tags:
                buckets.setdefault(tag, []).append(r)
        stats: dict[str, TagStat] = {}
        for tag, rs in sorted(buckets.items()):
            stats[tag] = TagStat(
                tag=tag,
                count=len(rs),
                mean_score=sum(r.score for r in rs) / len(rs),
                passed=sum(1 for r in rs if r.passed),
            )
        return stats

    def tag_scores(self) -> dict[str, float]:
        """``{tag: mean_score}`` — the slice the gate diffs against a baseline."""

        return {tag: stat.mean_score for tag, stat in self.by_tag().items()}

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable summary (what :func:`save_baseline` stores)."""

        return {
            "mean_score": round(self.mean_score, 6),
            "pass_rate": round(self.pass_rate, 6),
            "total": self.total,
            "passed": self.passed,
            "threshold": self.threshold,
            "tag_scores": {k: round(v, 6) for k, v in self.tag_scores().items()},
        }

    def render(self) -> str:
        """A compact text report for the console / CI logs."""

        lines = [
            "Eval report",
            "-" * 40,
            f"cases     : {self.total}",
            f"passed    : {self.passed}/{self.total} ({self.pass_rate:.0%})",
            f"mean score: {self.mean_score:.3f}  (threshold {self.threshold:.2f})",
            "",
            "Per-tag breakdown:",
        ]
        for tag, stat in self.by_tag().items():
            lines.append(
                f"  {tag:<22} {stat.mean_score:.3f}  "
                f"({stat.passed}/{stat.count} passed)"
            )
        if self.failures:
            lines.append("")
            lines.append("Failures:")
            for r in self.failures:
                lines.append(f"  x {r.case_id:<20} {r.score:.2f}  {r.rationale}")
        return "\n".join(lines)


# ======================================================================================
# Runner
# ======================================================================================


def _pick_grader(selector: GraderSelector, case: Case) -> Grader:
    if isinstance(selector, Grader):
        return selector
    return selector(case)


def run_suite(
    candidate: Candidate,
    cases: Sequence[Case],
    grader: GraderSelector,
    *,
    threshold: float = DEFAULT_PASS_THRESHOLD,
) -> Report:
    """Run ``candidate`` over ``cases``, grade each, and aggregate into a :class:`Report`.

    A candidate that raises on one input does not abort the run: that case scores ``0`` with
    the exception in its rationale, so one flaky case can't hide the rest of the suite.
    """

    results: list[CaseResult] = []
    for case in cases:
        g = _pick_grader(grader, case)
        try:
            output = candidate(case.input)
        except Exception as exc:
            results.append(
                CaseResult(
                    case_id=case.id,
                    tags=case.tags,
                    score=0.0,
                    passed=False,
                    rationale=f"candidate raised: {exc}",
                    output=None,
                )
            )
            continue
        gr: GradeResult = g.grade(case.expected, output)
        results.append(
            CaseResult(
                case_id=case.id,
                tags=case.tags,
                score=gr.score,
                passed=gr.score >= threshold,
                rationale=gr.rationale,
                output=output,
            )
        )
    return Report(results=tuple(results), threshold=threshold)


def run_grouped(
    candidate: Candidate,
    cases: Sequence[Case],
    graders: Mapping[str, Grader],
    *,
    default: Grader,
    threshold: float = DEFAULT_PASS_THRESHOLD,
) -> Report:
    """Pick a grader by the case's **first** matching tag, falling back to ``default``.

    Lets a dataset route ``json`` cases to :class:`~evals.graders.JSONSchemaMatch` and
    ``open-ended`` cases to the LLM-judge without per-case wiring at the call site.
    """

    def selector(case: Case) -> Grader:
        for tag in case.tags:
            if tag in graders:
                return graders[tag]
        return default

    return run_suite(candidate, cases, selector, threshold=threshold)


# ======================================================================================
# The CI gate
# ======================================================================================


@dataclass(frozen=True, slots=True)
class Regression:
    """One way the candidate fell below baseline."""

    scope: str  # "overall" or a tag name
    baseline: float
    current: float

    @property
    def drop(self) -> float:
        return self.baseline - self.current

    def __str__(self) -> str:
        return (
            f"{self.scope}: {self.current:.3f} < baseline {self.baseline:.3f} "
            f"(drop {self.drop:.3f})"
        )


@dataclass(frozen=True, slots=True)
class GateResult:
    """The verdict of comparing a report to a baseline."""

    passed: bool
    regressions: tuple[Regression, ...]
    tolerance: float

    @property
    def exit_code(self) -> int:
        return EXIT_OK if self.passed else EXIT_REGRESSION

    def render(self) -> str:
        if self.passed:
            return f"PASS gate (tolerance {self.tolerance:.3f}); no regression."
        lines = [f"FAIL gate (tolerance {self.tolerance:.3f}):"]
        lines.extend(f"  - {r}" for r in self.regressions)
        return "\n".join(lines)


def save_baseline(report: Report, path: str | Path) -> None:
    """Write a report's summary to ``path`` as the accepted baseline (pretty JSON)."""

    Path(path).write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_baseline(path: str | Path) -> dict[str, Any]:
    """Load a committed baseline summary (as written by :func:`save_baseline`)."""

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"baseline not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def gate(
    report: Report,
    baseline: Mapping[str, Any],
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    check_tags: bool = True,
) -> GateResult:
    """Compare a fresh ``report`` to a ``baseline`` summary; flag regressions.

    A *new* tag (present now, absent in the baseline) is never a regression — you can add cases
    without tripping the gate. A *missing* tag (in baseline, gone now) is likewise not flagged
    here; dataset shrinkage is a dataset-review concern, not a quality regression.
    """

    regressions: list[Regression] = []

    base_overall = float(baseline.get("mean_score", 0.0))
    if report.mean_score < base_overall - tolerance:
        regressions.append(Regression("overall", base_overall, report.mean_score))

    if check_tags:
        base_tags: Mapping[str, float] = baseline.get("tag_scores", {})
        current_tags = report.tag_scores()
        for tag, base_score in base_tags.items():
            if tag not in current_tags:
                continue
            cur = current_tags[tag]
            if cur < float(base_score) - tolerance:
                regressions.append(Regression(tag, float(base_score), cur))

    return GateResult(
        passed=not regressions,
        regressions=tuple(regressions),
        tolerance=tolerance,
    )


# ======================================================================================
# CLI entrypoint — what a CI step invokes
# ======================================================================================


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_evals",
        description="Score a golden set and gate the build against a baseline.",
    )
    p.add_argument(
        "dataset",
        type=str,
        help="path to a golden-set .jsonl (a bare name resolves under evals/datasets/).",
    )
    p.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="baseline JSON to compare against (write one first with --update).",
    )
    p.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE,
        help=f"allowed drop before failing (default {DEFAULT_TOLERANCE}).",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_PASS_THRESHOLD,
        help=f"per-case pass bar for the report (default {DEFAULT_PASS_THRESHOLD}).",
    )
    p.add_argument(
        "--update",
        action="store_true",
        help="run, then OVERWRITE the baseline with the new scores and exit 0.",
    )
    p.add_argument(
        "--no-tags",
        action="store_true",
        help="gate on the overall mean only (skip per-tag regression checks).",
    )
    return p


def default_graders() -> dict[str, Grader]:
    """Map a tag to the grader it routes to (the platform's standard grading policy).

    A case is graded by the grader for its **first** matching tag (see :func:`run_grouped`),
    falling back to :class:`ExactMatch`. This is the single place to read which capability is
    checked how: deterministic checks for closed-form/format/JSON answers, and the calibrated
    :class:`LLMJudge` (offline mock in CI) for the open-ended and ``must-refuse`` slices.
    """

    return {
        "exact": ExactMatch(),
        "contains": Contains(),
        "regex": RegexMatch(use_expected=True),
        "json": JSONSchemaMatch(),
        "tool-output": JSONSchemaMatch(),
        "open-ended": LLMJudge(),
        "must-refuse": LLMJudge(),
        "safety": LLMJudge(),
    }


def _identity_candidate(value: Any) -> Any:
    """Default candidate for the CLI: echo the input.

    The CLI is *thin demo wiring* — real use imports :func:`run_suite`/:func:`gate` and passes
    the platform's own agent + graders. The committed golden set is authored so the echo
    candidate exercises every grader (an exact answer echoes its expected value, the JSON case
    echoes a valid object, the regex case echoes a matching string, the refusal case echoes a
    refusal). That gives a meaningful baseline and proves the CI gate wiring end-to-end before
    a real agent is wired in.
    """

    return value


def main(argv: list[str] | None = None) -> int:
    """CLI: ``python -m evals.run_evals dataset.jsonl --baseline baseline.json``.

    Returns the process exit code (``0`` ok / ``1`` regression / ``2`` usage), so it can be
    used directly as ``sys.exit(main())`` and as a CI gate step.
    """

    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        cases = load_jsonl(args.dataset)
    except FileNotFoundError as exc:
        parser.error(str(exc))

    report = run_grouped(
        _identity_candidate,
        cases,
        default_graders(),
        default=ExactMatch(),
        threshold=args.threshold,
    )
    print(report.render())

    if args.update:
        save_baseline(report, args.baseline)
        print(f"\nBaseline written to {args.baseline}.")
        return EXIT_OK

    if not args.baseline.exists():
        print(
            f"\nNo baseline at {args.baseline}. Create one with --update.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    result = gate(
        report,
        load_baseline(args.baseline),
        tolerance=args.tolerance,
        check_tags=not args.no_tags,
    )
    print()
    print(result.render())
    return result.exit_code


if __name__ == "__main__":  # pragma: no cover
    # Honour the repo-wide MOCK default; the gate itself never spends.
    os.environ.setdefault("COMPANION_MOCK", "1")
    raise SystemExit(main())
