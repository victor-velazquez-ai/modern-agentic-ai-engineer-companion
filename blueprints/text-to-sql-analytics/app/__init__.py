"""The Talk-to-Your-Data analytics copilot — a SOLUTION blueprint (Appendix G).

This package *composes* four pattern blueprints (it does not fork them — see ``_compose.py``):

* **rag-pipeline** grounds NL on the semantic layer's schema/metric docs (``nl_to_sql.py``);
* **agent-loop** drives the generate -> verify -> execute -> render cycle (``pipeline.py``);
* **observability-stack** traces each stage with cost/SQL attributes (``pipeline.py``);
* **eval-harness** scores question -> expected answers (``../evals/run_evals.py``).

The public surface is the :class:`~app.pipeline.AnalyticsCopilot` and its :class:`CopilotAnswer`.
Everything runs **free and offline** in MOCK mode (the default); no API spend, secrets from env.
"""

from __future__ import annotations

from .nl_to_sql import SqlGenerator, SqlPlan, generate_sql
from .pipeline import AnalyticsCopilot, CopilotAnswer, answer_question
from .run import ExecutionError, QueryResult, run_query
from .semantic import SemanticLayer, load_semantic_layer
from .verify import QueryVerifier, VerifyResult, verify_plan

__all__ = [
    "AnalyticsCopilot",
    "CopilotAnswer",
    "answer_question",
    "SqlGenerator",
    "SqlPlan",
    "generate_sql",
    "QueryVerifier",
    "VerifyResult",
    "verify_plan",
    "QueryResult",
    "ExecutionError",
    "run_query",
    "SemanticLayer",
    "load_semantic_layer",
]
