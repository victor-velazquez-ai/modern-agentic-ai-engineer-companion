"""The grader contract.

A grader is anything that, given a case's ``expected`` reference and the candidate's actual
output, returns a :class:`GradeResult` — a score in ``[0, 1]`` and a short human rationale.
Keeping it to a tiny :class:`Grader` ``Protocol`` means *anything* with the right shape
plugs in: a class, a closure, a lambda — no base class to inherit, no registry to touch.

The rationale is not decoration. When an eval fails in CI, "score 0.0: expected JSON object,
got prose" is the difference between a five-second fix and a debugging session.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class GradeResult:
    """The outcome of grading one candidate output.

    Attributes
    ----------
    score:
        A float in ``[0, 1]``. ``1.0`` is a full pass; ``0.0`` a full fail. Graders may
        return partial credit (e.g. token overlap), so downstream code thresholds the score
        rather than treating it as a boolean.
    rationale:
        One short line explaining the score — surfaced in the report and the gate diff.
    passed:
        Convenience boolean at the default 0.5 bar; the runner re-thresholds explicitly.
    """

    score: float
    rationale: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be in [0, 1], got {self.score!r}")

    @property
    def passed(self) -> bool:
        return self.score >= 0.5

    @classmethod
    def fail(cls, rationale: str) -> "GradeResult":
        return cls(0.0, rationale)

    @classmethod
    def ok(cls, rationale: str = "match") -> "GradeResult":
        return cls(1.0, rationale)


@runtime_checkable
class Grader(Protocol):
    """Structural type for a grader: ``grade(expected, actual) -> GradeResult``.

    Implementations should be **pure and deterministic** where possible (the LLM-judge is the
    documented exception). They must never raise on bad candidate output — a malformed answer
    is a *score of 0 with a rationale*, not an exception, so one broken case can't crash a run.
    """

    def grade(self, expected: Any, actual: Any) -> GradeResult: ...
