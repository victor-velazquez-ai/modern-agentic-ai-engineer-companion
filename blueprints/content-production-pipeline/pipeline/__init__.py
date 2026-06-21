"""content_production_pipeline — a *solution* that composes the pattern blueprints.

This package is the Appendix-G "Content production pipeline" use case: a staged,
human-in-the-loop content workflow (brief -> research -> draft -> critique -> variants ->
guardrails -> review) built by **composing** the repo's pattern blueprints, not by forking
them:

* ``agent-loop``          -> the per-stage draft + reflection/critique loop (Ch 16).
* ``rag-pipeline``        -> retrieval over brand guidelines + product facts (Ch 13), so
  drafts stay on-message and don't fabricate claims.
* ``eval-harness``        -> brand-adherence + factual-accuracy evals + a CI gate (Ch 22).
* ``observability-stack`` -> a span per stage, so the whole pipeline is one auditable trace.
* ``llm-gateway``         -> (live path) the single door for the model calls behind every stage.

The composition seam lives in :mod:`pipeline.compose`: it puts each sibling blueprint's
``src/`` on ``sys.path`` and re-exports the symbols this solution uses. Nothing here edits a
blueprint; we only import them.

Everything runs **free, offline, and deterministically** under ``COMPANION_MOCK=1`` (the repo
default). The live path is documented at each seam and fails loud rather than spending money
behind your back.
"""

from __future__ import annotations

from .artifacts import Artifact, PipelineRun, Stage
from .guardrails import GuardrailFinding, GuardrailReport, check_brand_compliance
from .stages import (
    BrandContext,
    ContentPipeline,
    PipelineResult,
    build_brand_context,
)

__all__ = [
    # stages / orchestration
    "ContentPipeline",
    "PipelineResult",
    "BrandContext",
    "build_brand_context",
    # artifacts
    "Artifact",
    "PipelineRun",
    "Stage",
    # guardrails
    "check_brand_compliance",
    "GuardrailReport",
    "GuardrailFinding",
]

__version__ = "0.1.0"
