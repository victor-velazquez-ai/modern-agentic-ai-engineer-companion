"""research_due_diligence — a SOLUTION blueprint that *composes* pattern blueprints.

This package is the Appendix-G **Research & due-diligence agent**: ask a question, fan
retrieval/worker agents across many sources, and synthesize a **cited** brief whose every
claim links back to a retrieved source. A reflection pass flags any claim that is not
grounded — because for due diligence, *citations are the product*.

It is deliberately thin. The heavy lifting lives in five sibling **pattern blueprints**,
imported (not forked) from their own ``src/`` trees:

* ``multi-agent-supervisor`` — planner → retrieval/worker agents → synthesizer topology.
* ``rag-pipeline``           — chunk → embed → hybrid-retrieve → rerank over the corpus.
* ``agent-loop``             — the per-worker tool-use + reflection loop seam.
* ``eval-harness``           — citation-faithfulness + coverage evals.
* ``observability-stack``    — trace the run; attach token/cost; enforce step/cost caps.

Everything runs **free and offline in MOCK mode** (``COMPANION_MOCK=1``, the default): no
API key, no spend, deterministic output. See :mod:`app._compose` for exactly where the
sibling packages are put on the path, and :mod:`app.pipeline` for the end-to-end run.
"""

from __future__ import annotations

from .corpus import Source, load_corpus
from .pipeline import DueDiligenceAgent, DueDiligenceReport, build_agent
from .planner import SubQuestion, plan_questions
from .reflect import Claim, ReflectionReport, reflect
from .synthesize import CitedBrief, CitedClaim, synthesize
from .workers import Evidence, RetrievalWorker, build_retriever

__all__ = [
    # corpus
    "Source",
    "load_corpus",
    # planner (composes multi-agent-supervisor)
    "SubQuestion",
    "plan_questions",
    # workers (compose rag-pipeline + agent-loop)
    "Evidence",
    "RetrievalWorker",
    "build_retriever",
    # synthesize
    "CitedBrief",
    "CitedClaim",
    "synthesize",
    # reflect (the verification pass)
    "Claim",
    "ReflectionReport",
    "reflect",
    # end-to-end pipeline
    "DueDiligenceAgent",
    "DueDiligenceReport",
    "build_agent",
]

__version__ = "0.1.0"
