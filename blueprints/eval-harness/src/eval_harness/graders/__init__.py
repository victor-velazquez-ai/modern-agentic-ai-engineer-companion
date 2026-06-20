"""Graders — the pluggable scoring functions an eval set is run through.

A grader takes a case's ``expected`` and the candidate's actual output and returns a
:class:`~eval_harness.graders.base.GradeResult` (a score in ``[0, 1]`` plus a rationale).

Two families:

* **Deterministic** (:mod:`eval_harness.graders.deterministic`) — exact / contains / regex /
  JSON-schema. Fast, free, reproducible. Reach for these first.
* **LLM-judge** (:mod:`eval_harness.graders.llm_judge`) — rubric-based scoring for
  open-ended quality where no string check fits. Defaults to a deterministic *mock* judge so
  the harness stays free and reproducible standalone.
"""

from __future__ import annotations

from .base import GradeResult, Grader
from .deterministic import Contains, ExactMatch, JSONSchemaMatch, RegexMatch
from .llm_judge import LLMJudge, mock_judge

__all__ = [
    "Grader",
    "GradeResult",
    "ExactMatch",
    "Contains",
    "RegexMatch",
    "JSONSchemaMatch",
    "LLMJudge",
    "mock_judge",
]
