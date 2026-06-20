"""Rubric-based LLM-as-judge — with a deterministic mock judge as the default.

Some quality is open-ended: "is this summary faithful?", "is this refusal appropriate?".
No string check fits, so a model scores the candidate against a rubric. That power comes
with a tax — judges are **biased and noisy** (position/verbosity/self-preference bias,
run-to-run variance) — so this grader is built to *bound* that, and to never cost money or
flap unless you explicitly opt in.

How it stays free & deterministic
---------------------------------
The judge calls a ``JudgeModel`` — ``(prompt: str) -> str`` returning a JSON verdict. The
default is :func:`mock_judge`: a rule-based, seeded stand-in that reads ``expected``/``actual``
and emits a plausible verdict with **no API call**. This is what runs in ``MOCK=1`` (the
repo default), in CI, and for any reader without a key.

The live path
-------------
In ``MOCK=0`` you pass a real ``JudgeModel`` that routes through the **``llm-gateway``**
blueprint (``../../../llm-gateway/``) — the single door for model calls (routing, caching,
cost metering, guards). ``from_gateway`` wires that for you and is imported lazily so the
harness still imports with only the stdlib + ``requirements.txt`` installed.

Bounding judge bias/variance (see the README): pin the judge model + temperature 0, average
``samples`` votes, randomize answer position, and **anchor** every rubric level with a
concrete description so the score means the same thing across cases.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .base import GradeResult

# A judge model is just text-in / text-out. The text out should be a JSON verdict:
#   {"score": <0..1 or 1..N>, "rationale": "..."}
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
    and scores them with a cheap, seeded heuristic (exact match -> 5, high token overlap ->
    4, some overlap -> 3, little -> 2, none -> 1). The point is a *realistic, reproducible*
    verdict so notebooks/tests exercise the full judge code path for free.
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
        ``MOCK=0`` supply a gateway-backed callable (see :func:`from_gateway`).
    rubric:
        The scoring instructions. Anchor every level for stable, comparable scores.
    scale:
        The integer top of the judge's scale (default 5). Scores are normalized to ``[0, 1]``
        by ``(score - 1) / (scale - 1)`` so the harness speaks one language across graders.
    samples:
        How many votes to average. >1 reduces judge variance at linear cost; the mock judge
        is deterministic so one sample suffices for it.
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
            f"REFERENCE: {_stringify(expected)}\n"
            f"CANDIDATE: {_stringify(actual)}\n"
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
    def from_gateway(model: str = "claude-sonnet-4-5", **kwargs: Any) -> "LLMJudge":
        """Build a judge whose model calls route through the ``llm-gateway`` blueprint.

        Lazily imported so the harness still imports with only the stdlib installed. On the
        live path the gateway owns routing/caching/cost/guards — the harness just asks it for
        a verdict. Falls back to the mock judge whenever ``COMPANION_MOCK`` is set.
        """

        if _is_mock():
            return LLMJudge(model=mock_judge, **kwargs)

        def call(prompt: str) -> str:  # pragma: no cover - exercised only on live path
            # Import is local on purpose: `llm-gateway` is a sibling blueprint and is only
            # needed for real spend. Standalone/MOCK runs never reach here.
            from llm_gateway import LLMClient  # type: ignore[import-not-found]

            client = LLMClient()
            return client.complete(prompt, model=model, temperature=0)

        return LLMJudge(model=call, **kwargs)


def _stringify(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, sort_keys=True)


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
