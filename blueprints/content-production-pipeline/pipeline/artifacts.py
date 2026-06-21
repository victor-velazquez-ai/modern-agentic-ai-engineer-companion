"""Structured artifacts — one auditable record per stage (Ch 15).

A content pipeline is a *workflow*, not a chat: brief -> research -> draft -> critique ->
variants -> guardrails -> review. The senior move is to make every stage emit a **typed,
inspectable artifact** instead of passing a blob of text from one prompt to the next. That is
what lets you:

* answer "*why* did the variant say X?" by reading the research artifact it was grounded on;
* re-run one stage in isolation (feed its inputs, diff its output);
* attach any stage's output to an eval case or a trace span; and
* show a human reviewer the whole chain, not just the final string.

Nothing here is model-specific or vendor-specific — these are plain dataclasses. The
``observability-stack`` blueprint traces the *timing/cost* of each stage; these artifacts are the
*content* side of the same audit trail.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Stage(str, Enum):
    """The ordered stages of the pipeline. The value doubles as the span/artifact key."""

    BRIEF = "brief"
    RESEARCH = "research"
    DRAFT = "draft"
    CRITIQUE = "critique"
    REVISE = "revise"
    VARIANTS = "variants"
    GUARDRAILS = "guardrails"
    REVIEW = "review"

    def __str__(self) -> str:  # so f-strings / span names read cleanly
        return self.value


@dataclass(frozen=True, slots=True)
class Artifact:
    """One stage's output: the content it produced plus the provenance to audit it.

    Attributes
    ----------
    stage:
        Which :class:`Stage` produced this.
    content:
        The stage's primary output (text for draft/revise; structured data for research,
        variants, guardrails — kept as ``Any`` so a stage isn't forced to flatten to a string).
    sources:
        The retrieval ids / fact-keys this stage was grounded on (empty for stages that don't
        retrieve). This is the line you point at when asked "where did that claim come from?".
    meta:
        Free-form, stage-specific detail (token counts, scores, the critique's findings, etc.).
    """

    stage: Stage
    content: Any
    sources: tuple[str, ...] = field(default_factory=tuple)
    meta: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        """A one-line human summary for the console / review screen."""
        text = self.content if isinstance(self.content, str) else repr(self.content)
        clipped = text if len(text) <= 80 else text[:77] + "..."
        src = f"  ({len(self.sources)} sources)" if self.sources else ""
        return f"[{self.stage}] {clipped}{src}"


@dataclass(slots=True)
class PipelineRun:
    """An append-only ledger of the artifacts a single run produced.

    Mirrors the agent-loop's immutable transcript idea at the *pipeline* level: every stage
    appends exactly one artifact, so the run is replayable and inspectable after the fact. The
    review screen and the eval set both read this.
    """

    run_id: str
    brief_id: str
    artifacts: list[Artifact] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    review_ready: bool = False
    published: bool = False  # stays False by default: humans publish, the pipeline never does.

    def add(self, artifact: Artifact) -> Artifact:
        """Append a stage artifact and return it (so callers can chain)."""
        self.artifacts.append(artifact)
        return artifact

    def get(self, stage: Stage) -> Artifact | None:
        """The most recent artifact for ``stage``, or ``None`` if that stage didn't run."""
        for artifact in reversed(self.artifacts):
            if artifact.stage is stage:
                return artifact
        return None

    def require(self, stage: Stage) -> Artifact:
        """Like :meth:`get`, but raise if the stage is missing (a wiring bug, fail loud)."""
        found = self.get(stage)
        if found is None:
            raise KeyError(f"run {self.run_id!r} has no artifact for stage {stage!r}")
        return found

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable view of the run — what a review UI or audit log would store."""
        return {
            "run_id": self.run_id,
            "brief_id": self.brief_id,
            "review_ready": self.review_ready,
            "published": self.published,
            "stages": [
                {
                    "stage": str(a.stage),
                    "content": a.content,
                    "sources": list(a.sources),
                    "meta": a.meta,
                }
                for a in self.artifacts
            ],
        }
