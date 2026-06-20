"""Deterministic graders — exact / contains / regex / JSON-schema.

These are free, fast, and reproducible. Reach for them before an LLM-judge: most quality
bars (a tool emitted valid JSON, an answer named the right entity, output matched a format)
are checkable without a model in the loop, and a deterministic check never drifts.

Each grader returns a partial-credit-aware :class:`GradeResult` and **never raises** on
malformed candidate output — a bad answer is a score of ``0`` with a rationale.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .base import GradeResult


def _as_text(value: Any) -> str:
    """Coerce a candidate/expected value to text for string-shaped graders."""

    return value if isinstance(value, str) else json.dumps(value, sort_keys=True)


@dataclass(frozen=True, slots=True)
class ExactMatch:
    """Pass iff ``actual`` equals ``expected`` exactly.

    Strings are compared verbatim unless ``strip``/``ignore_case`` relax that; non-strings
    are compared by value. The strictest, cheapest grader — ideal for closed-form answers
    (a classification label, a slug, a number rendered as text).
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
    above zero — useful for "the answer must mention X, Y, and Z" rubrics. When
    ``needles`` is empty the case's own ``expected`` text is used as the single needle.
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

    The pattern usually comes from the grader config; pass ``use_expected=True`` to treat
    each case's ``expected`` field as the pattern instead (handy for per-case formats).
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
