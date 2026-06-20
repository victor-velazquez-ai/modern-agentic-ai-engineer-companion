"""The runner — score a candidate over a golden set and aggregate.

A *candidate* is the thing under test: ``(input) -> output``. Usually it's an agent or a
prompt, but it's just a callable, so a fixed string, a stub, or a recorded transcript all
work. The runner feeds each case's ``input`` to the candidate, grades the output against the
case's ``expected``, and rolls the per-case scores up into a :class:`Report` with an overall
mean **and a per-tag breakdown** — because a single accuracy number hides the regression
that only hit ``must-refuse`` cases.

Graders can be chosen globally (one grader for the whole set) or per case (a function of the
case), so a deterministic check and an LLM-judge can coexist in one run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from .dataset import Case
from .graders.base import GradeResult, Grader

# The system under test: given a case's input, produce an output to grade.
Candidate = Callable[[Any], Any]
# Either one grader for all cases, or a function that picks a grader per case.
GraderSelector = Grader | Callable[[Case], Grader]

DEFAULT_PASS_THRESHOLD = 0.5


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
        """JSON-serializable summary (what :func:`eval_harness.gate.save_baseline` stores)."""

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
                lines.append(f"  ✗ {r.case_id:<20} {r.score:.2f}  {r.rationale}")
        return "\n".join(lines)


def _pick_grader(selector: GraderSelector, case: Case) -> Grader:
    if isinstance(selector, Grader):
        return selector
    return selector(case)


def run(
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
    """Convenience: pick a grader by the case's **first** tag, falling back to ``default``.

    Lets a dataset route ``json`` cases to :class:`~eval_harness.graders.deterministic.JSONSchemaMatch`
    and ``open-ended`` cases to the LLM-judge without per-case wiring at the call site.
    """

    def selector(case: Case) -> Grader:
        for tag in case.tags:
            if tag in graders:
                return graders[tag]
        return default

    return run(candidate, cases, selector, threshold=threshold)
