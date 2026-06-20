"""Routing: map each sub-task to the worker best suited to run it.

The PLAN's hard question is *"which worker gets which sub-task?"*. This module is the
answer, kept as a small, testable policy rather than buried in the supervisor.

Two policies ship:

* :class:`KeywordRouter` — deterministic, offline, capability-tag matching. The default,
  because it runs free in MOCK and its decisions are assertable in tests.
* :class:`ModelRouter` — asks the model to pick a worker (the ``llm-gateway`` planning
  call from the PLAN). Falls back to the keyword router so it is safe in MOCK too.

A :class:`SubTask` already names a ``capability``; the router turns that into a concrete
worker, or reports that nothing can handle it (so the supervisor can degrade cleanly).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from .model import ModelPort
from .worker import Worker

# Capability hint keywords → capability tag, used to infer a tag from free text when a
# sub-task did not declare one. Order matters: first match wins.
_CAPABILITY_HINTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(research|investigat|find|gather|sources?|facts?|look up)\b", re.I), "research"),
    (re.compile(r"\b(writ|draft|summar|report|explain|compose|edit)\b", re.I), "write"),
    (re.compile(r"\b(cod|implement|program|function|debug|refactor)\b", re.I), "code"),
)


@dataclass(frozen=True)
class SubTask:
    """One unit of work the supervisor delegates.

    ``depends_on`` references other sub-task ids; sub-tasks with no unmet dependency
    are independent and may run in parallel (see ``aggregate``/``supervisor``).
    """

    id: str
    description: str
    capability: str = ""
    depends_on: tuple[str, ...] = ()

    def with_inferred_capability(self) -> "SubTask":
        """Return a copy with ``capability`` filled in from the text if it was blank."""
        if self.capability:
            return self
        for pattern, tag in _CAPABILITY_HINTS:
            if pattern.search(self.description):
                return SubTask(self.id, self.description, tag, self.depends_on)
        return SubTask(self.id, self.description, "general", self.depends_on)


class NoWorkerForTask(LookupError):
    """Raised when no worker advertises the required capability."""

    def __init__(self, subtask: SubTask) -> None:
        super().__init__(f"no worker can handle sub-task {subtask.id!r} (capability={subtask.capability!r})")
        self.subtask = subtask


@dataclass
class KeywordRouter:
    """Deterministic capability-tag router. The safe default.

    Matching is two-stage: first try an exact capability-tag match against each
    worker's advertised ``capabilities``; if the sub-task's tag is generic, fall back
    to scanning the description against every worker's tags. Ties break by worker order
    (stable, so tests are deterministic).
    """

    workers: Sequence[Worker]

    def route(self, subtask: SubTask) -> Worker:
        st = subtask.with_inferred_capability()
        tag = frozenset({st.capability})
        # Stage 1: direct capability match.
        for worker in self.workers:
            if worker.can_handle(tag):
                return worker
        # Stage 2: scan description tokens against worker capabilities.
        tokens = frozenset(re.findall(r"[a-z]+", st.description.lower()))
        best: Worker | None = None
        best_score = 0
        for worker in self.workers:
            score = len(worker.capabilities & tokens)
            if score > best_score:
                best, best_score = worker, score
        if best is not None:
            return best
        raise NoWorkerForTask(st)

    def route_all(self, subtasks: Sequence[SubTask]) -> list[tuple[SubTask, Worker]]:
        return [(st, self.route(st)) for st in subtasks]


@dataclass
class ModelRouter:
    """Model-driven router (the ``llm-gateway`` planning/routing call from the PLAN).

    It asks the model which worker fits, then validates the answer against the real
    roster. If the model picks something invalid — or we are in MOCK — it falls back
    to :class:`KeywordRouter`, so routing is never left to an unvalidated string.
    """

    workers: Sequence[Worker]
    model: ModelPort
    _fallback: KeywordRouter = field(init=False)

    def __post_init__(self) -> None:
        self._fallback = KeywordRouter(self.workers)

    def route(self, subtask: SubTask) -> Worker:
        roster = ", ".join(f"{w.name} ({w.role})" for w in self.workers)
        prompt = (
            f"Pick the single best worker for this sub-task.\n"
            f"Workers: {roster}\n"
            f"Sub-task: {subtask.description}\n"
            f"Answer with only the worker name."
        )
        resp = self.model.complete(prompt, system="You are a task router.", role="plan")
        picked = resp.text.strip().lower()
        for worker in self.workers:
            if worker.name.lower() in picked:
                return worker
        # Unvalidated / mock answer → deterministic fallback.
        return self._fallback.route(subtask)

    def route_all(self, subtasks: Sequence[SubTask]) -> list[tuple[SubTask, Worker]]:
        return [(st, self.route(st)) for st in subtasks]
