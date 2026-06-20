"""Pluggable scorers for the eval set.

A *scorer* takes one case's (expected, actual) pair and returns a ``Score``:
a pass/fail boolean in [0, 1] plus a short human-readable rationale. The runner
(:mod:`run.py`) calls one scorer per case and aggregates the results.

This file ships **stubs only** — there is intentionally NO business logic here.
Pick the scorer that fits each case (or write your own) and fill in the ``TODO``
blocks where your feature needs domain-specific checking.

Scorers provided:
    - ``exact``       deterministic, free  — string equality after normalization
    - ``contains``    deterministic, free  — expected substring appears in actual
    - ``regex``       deterministic, free  — actual matches a pattern
    - ``llm_judge``   model-graded         — rubric check, GATED by COMPANION_MOCK

The LLM-judge call is gated by the ``COMPANION_MOCK`` environment variable
(``1`` = canned verdict, free & offline & deterministic — the default). Only set
``COMPANION_MOCK=0`` when you have a key in ``.env`` and accept the token cost.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Score:
    """The outcome of scoring a single case."""

    passed: bool
    value: float  # in [0.0, 1.0]; 1.0 == pass, 0.0 == fail for boolean scorers
    rationale: str = ""

    @classmethod
    def of(cls, passed: bool, rationale: str = "") -> "Score":
        return cls(passed=passed, value=1.0 if passed else 0.0, rationale=rationale)


# A scorer takes (expected, actual) and returns a Score.
Scorer = Callable[[Any, Any], Score]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _norm(value: Any) -> str:
    """Normalize a value to a comparable string (lowercased, stripped).

    TODO: tune normalization for YOUR feature. Some suites should be
    case-sensitive, keep punctuation, or compare parsed JSON instead of text.
    """
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        # Compare structurally by canonical JSON (sorted keys).
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value).strip().lower()


def mock_enabled() -> bool:
    """True when canned (offline, free) mode is on. Defaults to ON."""
    return os.environ.get("COMPANION_MOCK", "1") != "0"


# ---------------------------------------------------------------------------
# Deterministic scorers (free, offline, no API)
# ---------------------------------------------------------------------------


def exact(expected: Any, actual: Any) -> Score:
    """Pass when ``actual`` equals ``expected`` after normalization."""
    ok = _norm(expected) == _norm(actual)
    return Score.of(ok, f"exact: expected={expected!r} actual={actual!r}")


def contains(expected: Any, actual: Any) -> Score:
    """Pass when the normalized ``expected`` is a substring of ``actual``."""
    ok = _norm(expected) in _norm(actual)
    return Score.of(ok, f"contains: looked for {expected!r} in {actual!r}")


def regex(pattern: str, actual: Any) -> Score:
    """Pass when ``actual`` matches the regular expression ``pattern``.

    Note the signature: ``(pattern, actual)`` — the "expected" slot is the regex.
    """
    ok = re.search(pattern, str(actual)) is not None
    return Score.of(ok, f"regex: /{pattern}/ against {actual!r}")


# ---------------------------------------------------------------------------
# LLM-judge scorer (model-graded) — GATED by COMPANION_MOCK
# ---------------------------------------------------------------------------

# TODO: write the rubric the judge applies. Keep it short and binary-friendly.
DEFAULT_RUBRIC = (
    "You are grading an AI answer. Reply with a JSON object "
    '{"pass": true|false, "reason": "<one sentence>"}. '
    "Pass only if the answer is factually correct and addresses the question."
)


def _mock_judge(expected: Any, actual: Any, rubric: str) -> Score:
    """Canned verdict for offline/CI runs — NO network, deterministic.

    The stub heuristic below exists only so the suite runs end-to-end with no
    API key. It is NOT a real judge.

    TODO: replace this with a fixture/recording strategy that matches how your
    team mocks model calls (e.g. a recorded-response file keyed by case id).
    """
    ok = bool(actual) and _norm(expected) in _norm(actual)
    return Score.of(ok, f"mock-judge: heuristic verdict (rubric len={len(rubric)})")


def _live_judge(expected: Any, actual: Any, rubric: str) -> Score:
    """Real LLM-judge call. Only reached when COMPANION_MOCK=0.

    TODO: implement using your model client. Sketch:

        from anthropic import Anthropic            # or your gateway
        client = Anthropic()                       # reads ANTHROPIC_API_KEY from .env
        resp = client.messages.create(
            model="claude-...-latest",             # TODO: pick the judge model
            max_tokens=256,
            system=rubric,
            messages=[{"role": "user", "content":
                f"QUESTION/EXPECTED:\n{expected}\n\nANSWER:\n{actual}"}],
        )
        verdict = json.loads(resp.content[0].text)
        return Score.of(bool(verdict["pass"]), verdict.get("reason", ""))

    Until you implement it, raise so a misconfigured live run fails loudly
    instead of silently passing everything.
    """
    raise NotImplementedError(
        "Live LLM-judge not implemented. Fill in _live_judge() in scorer.py, "
        "or keep COMPANION_MOCK=1 to use the offline mock judge."
    )


def llm_judge(expected: Any, actual: Any, rubric: str = DEFAULT_RUBRIC) -> Score:
    """Grade an open-ended answer with a model rubric.

    Gated by ``COMPANION_MOCK``: default ``1`` -> deterministic mock judge
    (free, offline); ``0`` -> real model call (requires a key in ``.env``).
    """
    if mock_enabled():
        return _mock_judge(expected, actual, rubric)
    return _live_judge(expected, actual, rubric)


# ---------------------------------------------------------------------------
# Dispatch: choose a scorer per case
# ---------------------------------------------------------------------------


def score_case(case: dict, actual: Any) -> Score:
    """Pick a scorer for ``case`` and apply it to the model's ``actual`` output.

    TODO: this is the one place with feature-specific routing. The default
    rules below are deliberately simple — customize them:
      - route ``must-refuse`` cases to a refusal detector,
      - use ``llm_judge`` for ``summarization``/open-ended tags,
      - fall back to ``contains`` otherwise.
    Replace with whatever mapping your suite needs.
    """
    tags = set(case.get("tags", []))
    expected = case.get("expected")

    # TODO: implement a real refusal check for safety cases.
    if "must-refuse" in tags:
        # Placeholder: treat any non-empty refusal-looking output as a pass.
        looks_like_refusal = any(
            w in _norm(actual) for w in ("cannot", "can't", "won't", "refuse", "unable")
        )
        return Score.of(looks_like_refusal, "refusal check (stub)")

    if tags & {"summarization", "open-ended"}:
        return llm_judge(expected, actual)

    # Default deterministic check.
    return contains(expected, actual)


__all__ = [
    "Score",
    "Scorer",
    "exact",
    "contains",
    "regex",
    "llm_judge",
    "score_case",
    "mock_enabled",
    "DEFAULT_RUBRIC",
]
