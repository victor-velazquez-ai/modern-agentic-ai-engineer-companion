"""The platform's evaluation harness (Appendix C · ``evals/``).

This is the *evaluate* station of the quality flywheel — the capstone's assembled
counterpart to the ``eval-harness`` blueprint. Where the blueprint shows the harness in
isolation (a ``src/eval_harness`` package), this is the same machinery wired into the
platform: golden sets that live next to the code in :mod:`evals.datasets`, a menu of
:mod:`graders`, a :func:`run_evals.run_suite` driver, and a CI **gate** that fails the build
when a gated metric regresses.

Layout (matches Appendix C, ``evals/`` with ``datasets/`` + ``run_evals.py``)
-----------------------------------------------------------------------------
``datasets/``      versioned golden sets (JSONL), reviewable in a PR.
``dataset.py``     the row schema ``{id, input, expected, tags[], notes}`` + JSONL loader.
``graders.py``     deterministic graders + a rubric LLM-judge (offline mock by default).
``run_evals.py``   load → score a candidate → aggregate per-tag → gate vs a baseline (CLI).

Everything runs **free and deterministic** with ``COMPANION_MOCK=1`` (the repo default): the
LLM-judge falls back to an offline mock verdict, so the suite — and CI — needs no API keys and
spends nothing. On the live path the judge routes through ``llm/gateway.py`` (the platform's
single door to model APIs); secrets are read from the environment only.
"""

from __future__ import annotations

from .dataset import Case, DatasetError, load_jsonl, parse_case, tags_of
from .graders import (
    Contains,
    ExactMatch,
    GradeResult,
    Grader,
    JSONSchemaMatch,
    LLMJudge,
    RegexMatch,
    mock_judge,
)
from .run_evals import (
    CaseResult,
    GateResult,
    Regression,
    Report,
    gate,
    load_baseline,
    run_suite,
    save_baseline,
)

__all__ = [
    # dataset
    "Case",
    "DatasetError",
    "load_jsonl",
    "parse_case",
    "tags_of",
    # graders
    "Grader",
    "GradeResult",
    "ExactMatch",
    "Contains",
    "RegexMatch",
    "JSONSchemaMatch",
    "LLMJudge",
    "mock_judge",
    # runner + gate
    "run_suite",
    "Report",
    "CaseResult",
    "gate",
    "GateResult",
    "Regression",
    "load_baseline",
    "save_baseline",
]

__version__ = "0.1.0"
