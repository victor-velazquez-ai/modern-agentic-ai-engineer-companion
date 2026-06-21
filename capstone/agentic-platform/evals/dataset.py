"""Golden-set schema and loader (Ch 22).

A golden set is a list of :class:`Case` rows stored as **JSONL** — one JSON object per line.
JSONL is the right shape for an eval set: it is appendable (add a case the day you find a
bug), diff-able, and reviewable in a pull request.

Row schema (the contract enforced here)::

    {"id": "...", "input": <any>, "expected": <any>, "tags": ["..."], "notes": "..."}

* ``id`` — unique, stable identifier. Required, non-empty.
* ``input`` — what the candidate (agent / prompt) is given. Required (any JSON type).
* ``expected`` — the reference answer / what a grader checks against. Required.
* ``tags`` — at least one. Tags are first-class so scores can be sliced by segment
  (capability, difficulty, ``must-refuse``, a regression-ticket id) instead of collapsing to a
  single accuracy number.
* ``notes`` — optional free text for reviewers.

This is the capstone's version of the ``eval-harness`` blueprint's ``dataset.py``; the schema
is identical on purpose so a golden set authored against the blueprint loads here unchanged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

# Golden sets live next to this module so they version with the code and review in a PR.
DATASETS_DIR = Path(__file__).resolve().parent / "datasets"


class DatasetError(ValueError):
    """Raised when a row violates the golden-set schema."""


@dataclass(frozen=True, slots=True)
class Case:
    """One golden-set row: an ``input``, its ``expected`` answer, and ``tags``."""

    id: str
    input: Any
    expected: Any
    tags: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.id or not isinstance(self.id, str):
            raise DatasetError("case 'id' must be a non-empty string")
        if not self.tags:
            raise DatasetError(f"case {self.id!r} must carry at least one tag")
        if not all(isinstance(t, str) and t for t in self.tags):
            raise DatasetError(f"case {self.id!r} has an empty/non-string tag")


def parse_case(obj: dict[str, Any]) -> Case:
    """Validate one decoded JSON object and build a :class:`Case`.

    Raises :class:`DatasetError` with a precise message on any missing/invalid field, so a bad
    dataset fails loudly in CI rather than silently scoring nothing.
    """

    if not isinstance(obj, dict):
        raise DatasetError(f"row must be a JSON object, got {type(obj).__name__}")

    missing = [k for k in ("id", "input", "expected") if k not in obj]
    if missing:
        raise DatasetError(f"row missing required field(s): {', '.join(missing)}")

    raw_tags = obj.get("tags", [])
    if not isinstance(raw_tags, list):
        raise DatasetError(f"case {obj.get('id')!r}: 'tags' must be a list")

    return Case(
        id=str(obj["id"]),
        input=obj["input"],
        expected=obj["expected"],
        tags=tuple(raw_tags),
        notes=str(obj.get("notes", "")),
    )


def load_jsonl(path: str | Path) -> list[Case]:
    """Load and validate a ``.jsonl`` golden set into a list of :class:`Case`.

    A bare filename (no separator) is resolved against :data:`DATASETS_DIR`, so callers can
    say ``load_jsonl("agent_golden.jsonl")`` from anywhere. Blank lines and ``#`` comment
    lines are skipped so a dataset can be lightly annotated. A duplicate ``id`` is an error —
    silently overwriting cases is how a golden set rots.
    """

    p = Path(path)
    if not p.is_absolute() and p.parent == Path("."):
        p = DATASETS_DIR / p
    if not p.exists():
        raise FileNotFoundError(f"dataset not found: {p}")

    cases: list[Case] = []
    seen: set[str] = set()
    for lineno, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetError(f"{p}:{lineno}: invalid JSON ({exc.msg})") from exc
        case = parse_case(obj)
        if case.id in seen:
            raise DatasetError(f"{p}:{lineno}: duplicate case id {case.id!r}")
        seen.add(case.id)
        cases.append(case)

    if not cases:
        raise DatasetError(f"{p}: dataset has no cases")
    return cases


def tags_of(cases: Iterable[Case]) -> list[str]:
    """Return the sorted set of tags present across ``cases`` (for per-tag breakdowns)."""

    out: set[str] = set()
    for c in cases:
        out.update(c.tags)
    return sorted(out)


def iter_jsonl(path: str | Path) -> Iterator[Case]:
    """Streaming variant of :func:`load_jsonl` for large sets (validates each row)."""

    yield from load_jsonl(path)
