"""Aggregation: fold many worker outputs into one answer the user can read.

The PLAN calls out aggregation strategy as a first-class trade-off. Three are provided:

* :func:`concat_aggregate` — join sections with headers. Cheap, lossless, offline.
  Good when each worker owns a distinct part of the answer.
* :func:`last_writer_aggregate` — take the final stage's output (the writer in a
  research→write pipeline). Good when later workers *consume* earlier ones.
* :class:`ModelAggregate` — ask the model to synthesize one coherent answer from all
  worker outputs. The richest, but costs a call; falls back to concat in MOCK-friendly
  ways so it stays runnable.

All of them ignore failed :class:`Outcome`s gracefully so a partial team still produces
a useful answer (degrade, don't crash).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .guards import Outcome
from .model import ModelPort
from .worker import WorkerResult


def _successful(results: Sequence[Outcome[WorkerResult]]) -> list[WorkerResult]:
    return [o.value for o in results if o.ok and o.value is not None]


def concat_aggregate(results: Sequence[Outcome[WorkerResult]]) -> str:
    """Join each successful worker's output under a role header. Order-preserving."""
    parts = [f"## {r.role.capitalize()} ({r.worker})\n{r.output}" for r in _successful(results)]
    if not parts:
        return "No worker produced an answer."
    return "\n\n".join(parts)


def last_writer_aggregate(results: Sequence[Outcome[WorkerResult]]) -> str:
    """Return the last successful output — the synthesis stage in a pipeline.

    Prefers a worker whose role looks like writing/editing; otherwise the last success.
    """
    ok = _successful(results)
    if not ok:
        return "No worker produced an answer."
    for r in reversed(ok):
        if any(k in r.role.lower() for k in ("writ", "edit", "summar")):
            return r.output
    return ok[-1].output


@dataclass
class ModelAggregate:
    """Synthesize one answer from all worker outputs via a model call.

    This is the supervisor's own model usage (planning/synthesis), distinct from the
    workers'. In MOCK it produces a deterministic synthesis; on the live path it would
    route through ``llm-gateway`` like every other call.
    """

    model: ModelPort

    def __call__(self, results: Sequence[Outcome[WorkerResult]]) -> str:
        ok = _successful(results)
        if not ok:
            return "No worker produced an answer."
        body = "\n\n".join(f"{r.role} said: {r.output}" for r in ok)
        prompt = (
            "Synthesize the worker outputs below into one coherent final answer. "
            "Resolve overlaps, keep it tight.\n\n" + body
        )
        return self.model.complete(prompt, system="You synthesize a team's work.", role="write").text


@dataclass
class AggregateReport:
    """A structured view of a finished run — answer plus provenance and cost."""

    answer: str
    contributions: tuple[WorkerResult, ...]
    failures: tuple[str, ...]
    total_tokens: int

    @property
    def degraded(self) -> bool:
        """True if at least one worker failed but the team still answered."""
        return bool(self.failures) and bool(self.contributions)


def build_report(results: Sequence[Outcome[WorkerResult]], answer: str) -> AggregateReport:
    """Assemble an :class:`AggregateReport` from raw worker outcomes and a final answer."""
    ok = _successful(results)
    failures = tuple(o.error or "unknown error" for o in results if o.failed)
    total = sum(r.total_tokens for r in ok)
    return AggregateReport(
        answer=answer,
        contributions=tuple(ok),
        failures=failures,
        total_tokens=total,
    )
