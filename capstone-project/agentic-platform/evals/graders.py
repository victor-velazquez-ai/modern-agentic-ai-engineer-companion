"""Graders (Ch 22) — the menu of ways to score a candidate output.

A grader is anything that, given a case's ``expected`` reference and the candidate's actual
output, returns a :class:`GradeResult` — a score in ``[0, 1]`` and a short human rationale.
Keeping it to a tiny :class:`Grader` ``Protocol`` means *anything* with the right shape plugs
in: a class, a closure, a lambda — no base class to inherit, no registry to touch.

The menu (reach for the cheapest that fits):

============== ============================================ =======================
Grader         Use it when                                  Scores
============== ============================================ =======================
ExactMatch     a closed-form answer (label, slug, number)   1.0 / 0.0
Contains       the answer must mention specific things      fraction of needles
RegexMatch     output must match a format                   1.0 / 0.0
JSONSchemaMatch a tool returned JSON of the right shape     1.0 / 0.0
LLMJudge       open-ended quality (faithful? refused well?) normalized rubric score
============== ============================================ =======================

Graders are **pure and never raise** on malformed candidate output — a bad answer is a score
of ``0`` with a rationale, so one broken case can't crash a run. The LLM-judge is the one
documented non-determinism, and even it runs an offline, deterministic mock verdict by default
(``COMPANION_MOCK=1``). On the live path the judge routes model calls through the platform's
``llm/gateway.py`` — the single door that owns routing, caching, cost metering, and guards.

This module flattens the blueprint's ``graders/`` package (``base`` + ``deterministic`` +
``llm_judge``) into one file to match Appendix C's leaner ``evals/`` shape.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

# ======================================================================================
# The grader contract
# ======================================================================================


@dataclass(frozen=True, slots=True)
class GradeResult:
    """The outcome of grading one candidate output.

    Attributes
    ----------
    score:
        A float in ``[0, 1]``. ``1.0`` is a full pass; ``0.0`` a full fail. Graders may return
        partial credit (e.g. token overlap), so downstream code thresholds the score rather
        than treating it as a boolean.
    rationale:
        One short line explaining the score — surfaced in the report and the gate diff. Not
        decoration: "score 0.0: expected JSON object, got prose" is a five-second fix instead
        of a debugging session.
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


def _as_text(value: Any) -> str:
    """Coerce a candidate/expected value to text for string-shaped graders."""

    return value if isinstance(value, str) else json.dumps(value, sort_keys=True)


# ======================================================================================
# Deterministic graders — free, fast, reproducible
# ======================================================================================


@dataclass(frozen=True, slots=True)
class ExactMatch:
    """Pass iff ``actual`` equals ``expected`` exactly.

    Strings are compared verbatim unless ``strip``/``ignore_case`` relax that; non-strings are
    compared by value. The strictest, cheapest grader — ideal for closed-form answers (a
    classification label, a slug, a number rendered as text).
    """

    strip: bool = True
    ignore_case: bool = False

    def _norm(self, v: Any) -> Any:
        if isinstance(v, str):
            if self.strip:
                v = v.strip()
            if self.ignore_case:
                v = v.lower()
        return v

    def grade(self, expected: Any, actual: Any) -> GradeResult:
        if self._norm(expected) == self._norm(actual):
            return GradeResult.ok("exact match")
        return GradeResult.fail(f"expected {expected!r}, got {actual!r}")


@dataclass(frozen=True, slots=True)
class Contains:
    """Pass iff every required substring appears in ``actual``.

    With several needles, awards **partial credit** (fraction found) so a near-miss scores
    above zero — useful for "the answer must mention X, Y, and Z" rubrics. When ``needles`` is
    empty the case's own ``expected`` text is used as the single needle.
    """

    needles: tuple[str, ...] = ()
    ignore_case: bool = True

    def grade(self, expected: Any, actual: Any) -> GradeResult:
        hay = _as_text(actual)
        needles = self.needles or (_as_text(expected),)
        if self.ignore_case:
            hay = hay.lower()
            needles = tuple(n.lower() for n in needles)
        found = [n for n in needles if n in hay]
        score = len(found) / len(needles)
        if score == 1.0:
            return GradeResult.ok(f"contains all {len(needles)} substring(s)")
        missing = [n for n in needles if n not in hay]
        return GradeResult(score, f"missing {missing!r}")


@dataclass(frozen=True, slots=True)
class RegexMatch:
    """Pass iff ``actual`` matches ``pattern`` (``re.search`` semantics).

    The pattern usually comes from the grader config; pass ``use_expected=True`` to treat each
    case's ``expected`` field as the pattern instead (handy for per-case formats).
    """

    pattern: str = ""
    flags: int = 0
    use_expected: bool = False

    def grade(self, expected: Any, actual: Any) -> GradeResult:
        pat = _as_text(expected) if self.use_expected else self.pattern
        try:
            compiled = re.compile(pat, self.flags)
        except re.error as exc:
            return GradeResult.fail(f"bad regex {pat!r}: {exc}")
        if compiled.search(_as_text(actual)) is not None:
            return GradeResult.ok(f"matched /{pat}/")
        return GradeResult.fail(f"no match for /{pat}/")


@dataclass(frozen=True, slots=True)
class JSONSchemaMatch:
    """Validate that ``actual`` is JSON of the right shape.

    A deliberately small, dependency-free schema: ``type`` (``object``/``array``/``string``/
    ``number``/``integer``/``boolean``/``null``) and, for objects, ``required`` keys and a
    ``properties`` map of nested schemas. This covers the common agent check — "the tool
    returned a JSON object with these fields" — without pulling in ``jsonschema``.

    When ``schema`` is omitted, the case's ``expected`` value is used as the schema, so a
    dataset can carry a per-case shape inline.
    """

    schema: dict[str, Any] | None = None

    def grade(self, expected: Any, actual: Any) -> GradeResult:
        schema = self.schema if self.schema is not None else expected
        if not isinstance(schema, dict):
            return GradeResult.fail("no JSON schema provided")

        value = actual
        if isinstance(actual, str):
            try:
                value = json.loads(actual)
            except json.JSONDecodeError as exc:
                return GradeResult.fail(f"not valid JSON: {exc.msg}")

        ok, why = _validate(value, schema)
        return GradeResult.ok("schema valid") if ok else GradeResult.fail(why)


_PY_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "null": (type(None),),
}


def _validate(value: Any, schema: dict[str, Any], path: str = "$") -> tuple[bool, str]:
    """Tiny recursive validator returning ``(ok, reason_if_not)``."""

    expected_type = schema.get("type")
    if expected_type is not None:
        py = _PY_TYPES.get(expected_type)
        if py is None:
            return False, f"{path}: unknown schema type {expected_type!r}"
        # bool is a subclass of int — keep them distinct for "integer"/"number".
        if expected_type in ("number", "integer") and isinstance(value, bool):
            return False, f"{path}: expected {expected_type}, got boolean"
        if not isinstance(value, py):
            got = type(value).__name__
            return False, f"{path}: expected {expected_type}, got {got}"

    if expected_type == "object" or (expected_type is None and isinstance(value, dict)):
        if not isinstance(value, dict):
            return False, f"{path}: expected object, got {type(value).__name__}"
        for key in schema.get("required", []):
            if key not in value:
                return False, f"{path}: missing required key {key!r}"
        for key, subschema in schema.get("properties", {}).items():
            if key in value:
                ok, why = _validate(value[key], subschema, f"{path}.{key}")
                if not ok:
                    return False, why

    if expected_type == "array" and "items" in schema and isinstance(value, list):
        for i, item in enumerate(value):
            ok, why = _validate(item, schema["items"], f"{path}[{i}]")
            if not ok:
                return False, why

    return True, ""


# ======================================================================================
# LLM-as-judge — rubric scoring for the open-ended slice (offline mock by default)
# ======================================================================================

# A judge model is just text-in / text-out. The text out should be a JSON verdict:
#   {"score": <1..N>, "rationale": "..."}
JudgeModel = Callable[[str], str]


DEFAULT_RUBRIC = (
    "Score how well the CANDIDATE answer matches the REFERENCE for the given task.\n"
    "5 = fully correct and complete; 4 = minor omission; 3 = partially correct;\n"
    "2 = mostly wrong; 1 = wrong or off-topic. Reply with JSON only: "
    '{"score": <1-5>, "rationale": "<one sentence>"}.'
)


def _is_mock() -> bool:
    """True when the harness must not spend tokens (the repo-wide default)."""

    return os.getenv("COMPANION_MOCK", "1") != "0"


def mock_judge(prompt: str) -> str:
    """A deterministic, offline stand-in for a real judge model.

    It does not call any API. It extracts the REFERENCE and CANDIDATE blocks from the prompt
    and scores them with a cheap, seeded heuristic (exact match -> 5, high token overlap -> 4,
    some overlap -> 3, little -> 2, none -> 1). The point is a *realistic, reproducible*
    verdict so the suite and tests exercise the full judge code path for free.
    """

    ref = _extract(prompt, "REFERENCE")
    cand = _extract(prompt, "CANDIDATE")
    score_5 = _heuristic_score(ref, cand)
    rationale = {
        5: "candidate matches the reference",
        4: "candidate covers most of the reference",
        3: "candidate partially overlaps the reference",
        2: "candidate largely diverges from the reference",
        1: "candidate is unrelated to the reference",
    }[score_5]
    return json.dumps({"score": score_5, "rationale": rationale})


def _extract(prompt: str, label: str) -> str:
    m = re.search(rf"{label}:\s*(.*?)(?:\n[A-Z]+:|\Z)", prompt, re.DOTALL)
    return (m.group(1).strip() if m else "").lower()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def _heuristic_score(ref: str, cand: str) -> int:
    if not cand:
        return 1
    if ref and ref == cand:
        return 5
    rt, ct = _tokens(ref), _tokens(cand)
    if not rt:
        return 3
    overlap = len(rt & ct) / len(rt)
    if overlap >= 0.99:
        return 5
    if overlap >= 0.6:
        return 4
    if overlap >= 0.3:
        return 3
    if overlap > 0.0:
        return 2
    return 1


@dataclass(frozen=True, slots=True)
class LLMJudge:
    """Grade open-ended quality with a model judge (mock by default).

    Parameters
    ----------
    model:
        A ``JudgeModel`` callable. Defaults to :func:`mock_judge` (offline, free). In
        ``MOCK=0`` supply a gateway-backed callable (see :meth:`from_gateway`).
    rubric:
        The scoring instructions. Anchor every level for stable, comparable scores.
    scale:
        The integer top of the judge's scale (default 5). Scores normalize to ``[0, 1]`` via
        ``(score - 1) / (scale - 1)`` so the harness speaks one language across graders.
    samples:
        How many votes to average. >1 reduces judge variance at linear cost; the mock judge is
        deterministic so one sample suffices for it.
    """

    model: JudgeModel = mock_judge
    rubric: str = DEFAULT_RUBRIC
    scale: int = 5
    samples: int = 1
    extra_context: str = field(default="", repr=False)

    def _prompt(self, expected: Any, actual: Any) -> str:
        return (
            f"{self.rubric}\n\n"
            f"TASK: {self.extra_context or 'Judge the candidate against the reference.'}\n"
            f"REFERENCE: {_as_text(expected)}\n"
            f"CANDIDATE: {_as_text(actual)}\n"
        )

    def _normalize(self, raw_score: float) -> float:
        if self.scale <= 1:
            return max(0.0, min(1.0, float(raw_score)))
        norm = (float(raw_score) - 1.0) / (self.scale - 1.0)
        return max(0.0, min(1.0, norm))

    def grade(self, expected: Any, actual: Any) -> GradeResult:
        prompt = self._prompt(expected, actual)
        scores: list[float] = []
        rationale = ""
        for _ in range(max(1, self.samples)):
            try:
                verdict = _parse_verdict(self.model(prompt))
            except Exception as exc:  # judge must degrade, never crash the run
                return GradeResult.fail(f"judge error: {exc}")
            scores.append(self._normalize(verdict["score"]))
            rationale = verdict["rationale"]
        mean = sum(scores) / len(scores)
        suffix = "" if self.samples == 1 else f" (mean of {self.samples})"
        return GradeResult(mean, f"judge: {rationale}{suffix}")

    @staticmethod
    def from_gateway(model: str = "claude-haiku-4-5", **kwargs: Any) -> "LLMJudge":
        """Build a judge whose model calls route through the platform ``llm/gateway.py``.

        Lazily imported so the harness still imports with only the stdlib installed. On the
        live path the gateway owns routing/caching/cost/guards — the harness just asks it for a
        verdict. Falls back to the mock judge whenever ``COMPANION_MOCK`` is set, so CI never
        spends. Pin a *cheap* judge model at the lowest effort that still discriminates.
        """

        if _is_mock():
            return LLMJudge(model=mock_judge, **kwargs)

        def call(prompt: str) -> str:  # pragma: no cover - exercised only on live path
            # Local import: the gateway is the platform's model door and only needed for real
            # spend. Standalone/MOCK runs never reach here.
            from llm.gateway import Gateway  # type: ignore[import-not-found]

            return Gateway().complete(prompt, model=model)

        return LLMJudge(model=call, **kwargs)


def _parse_verdict(text: str) -> dict[str, Any]:
    """Parse a judge's JSON reply, tolerating surrounding prose / code fences."""

    candidate = text.strip()
    m = re.search(r"\{.*\}", candidate, re.DOTALL)
    if m:
        candidate = m.group(0)
    obj = json.loads(candidate)
    if "score" not in obj:
        raise ValueError("judge reply missing 'score'")
    return {"score": obj["score"], "rationale": str(obj.get("rationale", ""))}


__all__ = [
    "GradeResult",
    "Grader",
    "ExactMatch",
    "Contains",
    "RegexMatch",
    "JSONSchemaMatch",
    "LLMJudge",
    "mock_judge",
    "JudgeModel",
    "DEFAULT_RUBRIC",
]
