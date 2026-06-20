"""The supervisor: plan → delegate → aggregate → decide-done.

This is the orchestrator the PLAN describes. It:

1. **Plans** — decomposes a task into :class:`~multi_agent_supervisor.routing.SubTask`s
   (deterministically in MOCK; via the model on the live path).
2. **Routes** — sends each sub-task to the right worker (``routing``).
3. **Runs** — sequentially, or fans **independent** sub-tasks out in parallel and rejoins
   them, while respecting dependencies.
4. **Isolates failure** — a worker that crashes becomes a recorded failure, not a crash;
   the team degrades.
5. **Aggregates** — folds worker outputs into one answer (``aggregate``).
6. **Decides done** — stops when every sub-task has a result (or a guard trips), and
   reports *why* it stopped.

The control flow is intentionally readable: no framework hides when the supervisor
delegates, parallelizes, or halts.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Sequence

from .aggregate import AggregateReport, build_report, last_writer_aggregate
from .guards import DepthGuard, GuardTripped, IterationGuard, Outcome
from .model import ModelPort, build_model, looks_like_injection
from .routing import KeywordRouter, SubTask
from .worker import Worker, WorkerResult, default_team


class DoneReason(str, Enum):
    """Why the supervisor stopped — asserted in tests, surfaced in the report."""

    COMPLETED = "completed"          # every sub-task produced a result
    DEGRADED = "degraded"            # finished, but one or more workers failed
    GUARD_TRIPPED = "guard_tripped"  # iteration/depth cap hit before completion
    REFUSED = "refused"              # task rejected before any work (e.g. injection)
    NO_PLAN = "no_plan"              # planner produced no sub-tasks


# A planner turns a task string into sub-tasks. Swappable so the live path can use the
# model; the default is deterministic and offline.
Planner = Callable[[str], list[SubTask]]
# An aggregator folds worker outcomes into one answer string.
Aggregator = Callable[[Sequence[Outcome[WorkerResult]]], str]


def default_planner(task: str) -> list[SubTask]:
    """Deterministic two-stage plan: research the task, then write it up.

    This mirrors the PLAN's 2-worker (researcher + writer) demo. The writer depends on
    the researcher, so the two run *sequentially*; give a task two independent clauses
    (``" and "``) and the research stage fans out in parallel (see :meth:`Supervisor.run`).
    """
    clauses = [c.strip() for c in task.split(" and ") if c.strip()]
    if len(clauses) <= 1:
        research = [SubTask(id="research-1", description=f"Research: {task}", capability="research")]
    else:
        research = [
            SubTask(id=f"research-{i+1}", description=f"Research: {clause}", capability="research")
            for i, clause in enumerate(clauses)
        ]
    write = SubTask(
        id="write-1",
        description=f"Write the final answer to: {task}",
        capability="write",
        depends_on=tuple(r.id for r in research),
    )
    return [*research, write]


@dataclass
class RunResult:
    """Everything a run produced: the answer, why it stopped, and full provenance."""

    answer: str
    reason: DoneReason
    report: AggregateReport
    plan: tuple[SubTask, ...]
    iterations: int

    @property
    def ok(self) -> bool:
        return self.reason in {DoneReason.COMPLETED, DoneReason.DEGRADED}


@dataclass
class Supervisor:
    """Orchestrates a team of :class:`Worker`s to finish a task.

    Construct with :meth:`from_team` for the default config, or pass your own planner,
    router, aggregator, and guards. ``parallel=True`` fans independent sub-tasks out
    across a thread pool; dependent ones always wait for their inputs.
    """

    workers: Sequence[Worker]
    model: ModelPort
    planner: Planner = default_planner
    aggregator: Aggregator = last_writer_aggregate
    parallel: bool = True
    max_workers: int = 4
    iteration_guard: IterationGuard = field(default_factory=lambda: IterationGuard(max_iterations=8))
    depth_guard: DepthGuard = field(default_factory=lambda: DepthGuard(max_depth=3))

    # --- construction --------------------------------------------------------
    @classmethod
    def from_team(
        cls,
        *,
        mock: bool | None = None,
        parallel: bool = True,
    ) -> "Supervisor":
        """Build the canonical researcher+writer supervisor (the PLAN's demo team)."""
        model = build_model(mock=mock)
        return cls(workers=default_team(model), model=model, parallel=parallel)

    # --- the orchestration loop ---------------------------------------------
    def run(self, task: str) -> RunResult:
        router = KeywordRouter(self.workers)

        # Guard 0: refuse obviously hostile task text before spending anything.
        if looks_like_injection(task):
            empty = build_report([], "Task refused: it contains injected instructions.")
            return RunResult(empty.answer, DoneReason.REFUSED, empty, (), 0)

        # 1) PLAN.
        plan = self.planner(task)
        if not plan:
            empty = build_report([], "No plan could be formed for this task.")
            return RunResult(empty.answer, DoneReason.NO_PLAN, empty, (), 0)

        # Execute respecting dependencies. Each dependency "wave" is one iteration; within
        # a wave, independent sub-tasks run in parallel (or sequentially if disabled).
        done: dict[str, Outcome[WorkerResult]] = {}
        ordered: list[Outcome[WorkerResult]] = []
        pending = list(plan)
        try:
            while pending:
                self.iteration_guard.tick()  # 4) bound the orchestration rounds
                ready = [st for st in pending if all(dep in done for dep in st.depends_on)]
                if not ready:
                    # A dependency can never be satisfied (cycle / unknown id) — stop clean.
                    break
                wave = self._run_wave(ready, router)
                for st, outcome in wave:
                    done[st.id] = outcome
                    ordered.append(outcome)
                pending = [st for st in pending if st.id not in done]
        except GuardTripped:
            answer = self.aggregator(ordered)
            report = build_report(ordered, answer)
            return RunResult(answer, DoneReason.GUARD_TRIPPED, report, tuple(plan), self.iteration_guard.count)

        # 5) AGGREGATE + 6) DECIDE DONE.
        answer = self.aggregator(ordered)
        report = build_report(ordered, answer)
        reason = self._decide_reason(plan=plan, done=done, report=report)
        return RunResult(answer, reason, report, tuple(plan), self.iteration_guard.count)

    # --- internals -----------------------------------------------------------
    def _run_wave(
        self,
        ready: Sequence[SubTask],
        router: KeywordRouter,
    ) -> list[tuple[SubTask, Outcome[WorkerResult]]]:
        """Run one dependency wave. Independent sub-tasks fan out and rejoin here."""
        assignments: list[tuple[SubTask, Worker]] = []
        for st in ready:
            try:
                assignments.append((st, router.route(st)))
            except LookupError:
                # No worker for this sub-task: record as a failed Outcome, keep going.
                assignments.append((st, _UnroutableWorker(st)))

        if not self.parallel or len(assignments) == 1:
            return [(st, worker.handle(st.description)) for st, worker in assignments]

        # Parallel fan-out across the wave, then rejoin in submission order.
        results: list[tuple[SubTask, Outcome[WorkerResult]]] = [None] * len(assignments)  # type: ignore[list-item]
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(assignments))) as pool:
            futures = {
                pool.submit(worker.handle, st.description): idx
                for idx, (st, worker) in enumerate(assignments)
            }
            for future in futures:
                idx = futures[future]
                st, _ = assignments[idx]
                results[idx] = (st, future.result())
        return results

    def _decide_reason(
        self,
        *,
        plan: Sequence[SubTask],
        done: dict[str, Outcome[WorkerResult]],
        report: AggregateReport,
    ) -> DoneReason:
        """The 'is the job finished?' decision, made explicit and testable."""
        all_attempted = all(st.id in done for st in plan)
        if not all_attempted:
            return DoneReason.GUARD_TRIPPED
        if report.failures:
            # Finished every sub-task, but some failed: degrade, don't claim success.
            return DoneReason.DEGRADED if report.contributions else DoneReason.GUARD_TRIPPED
        return DoneReason.COMPLETED


@dataclass
class _UnroutableWorker:
    """Stand-in 'worker' for a sub-task no real worker can handle.

    Its :meth:`handle` returns a failed :class:`Outcome`, so an unroutable sub-task
    degrades the run exactly like a crashed worker — uniform failure handling.
    """

    subtask: SubTask

    def handle(self, task: str) -> Outcome[WorkerResult]:
        return Outcome(
            ok=False,
            error=f"NoWorkerForTask: no worker for capability {self.subtask.capability!r}",
        )
