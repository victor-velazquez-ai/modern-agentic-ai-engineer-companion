"""eval_harness — a quality gate for agents.

The standalone version of the capstone ``evals/``: golden datasets (input -> expected),
a menu of pluggable **graders** (deterministic checks plus an **LLM-judge**), a **runner**
that scores a candidate over the set and breaks results down per tag, and a **gate** that
compares against a baseline and exits non-zero when quality regresses past a threshold.

Design goals
------------
* **Free & deterministic standalone.** Everything runs offline in ``MOCK=1`` (the default).
  The LLM-judge uses a canned, rule-based verdict so the harness never spends tokens unless
  you opt in.
* **Importable, stable surface.** This package depends on *no* other blueprint. Other
  blueprints and chapters import it; it imports none of them. On the live path the judge
  routes model calls through the ``llm-gateway`` blueprint (see ``graders.llm_judge``).
* **Tooling, not cells.** The dataset format, pluggable graders, baseline diffing, and a CI
  entrypoint with a non-zero exit on regression are exactly what the tests assert.

Quick start
-----------
>>> from eval_harness import Case, ExactMatch, run
>>> cases = [Case(id="greet", input="hi", expected="hello", tags=["smoke"])]
>>> report = run(lambda text: "hello", cases, ExactMatch())
>>> report.mean_score
1.0
"""

from __future__ import annotations

from .dataset import Case, load_jsonl, parse_case
from .graders.base import GradeResult, Grader
from .graders.deterministic import (
    Contains,
    ExactMatch,
    JSONSchemaMatch,
    RegexMatch,
)
from .graders.llm_judge import LLMJudge, mock_judge
from .gate import GateResult, gate, load_baseline, save_baseline
from .runner import CaseResult, Report, run

__all__ = [
    # dataset
    "Case",
    "load_jsonl",
    "parse_case",
    # grader contract
    "Grader",
    "GradeResult",
    # deterministic graders
    "ExactMatch",
    "Contains",
    "RegexMatch",
    "JSONSchemaMatch",
    # llm-judge
    "LLMJudge",
    "mock_judge",
    # runner
    "run",
    "Report",
    "CaseResult",
    # gate
    "gate",
    "GateResult",
    "load_baseline",
    "save_baseline",
]

__version__ = "0.1.0"
