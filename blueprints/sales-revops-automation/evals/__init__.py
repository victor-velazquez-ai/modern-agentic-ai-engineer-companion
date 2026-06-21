"""evals — the extraction-accuracy quality gate for the RevOps workflow (composes ``eval-harness``).

The golden set lives in ``extraction_golden.jsonl``; the candidate + grader that score it live in
:mod:`evals.harness`. Run ``python -m evals.harness`` (or call :func:`evals.harness.evaluate`) to
score the call->CRM stage offline and for free. This is the PLAN's "extraction-accuracy eval set"
plus the wrong-recipient guardrail check, built on the ``eval-harness`` pattern blueprint.
"""

from __future__ import annotations

__version__ = "0.1.0"
