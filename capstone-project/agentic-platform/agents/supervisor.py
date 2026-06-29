"""The multi-agent supervisor (Ch 17) — plan → delegate → aggregate → decide-done.

A supervisor owns the *goal and the budget*; the workers own the *doing*. This is the platform's
integrated version of the ``multi-agent-supervisor`` blueprint
(``blueprints/multi-agent-supervisor``): same orchestration shape, but each worker is a real
:class:`~agents.raw.AgentLoop` driven through the platform's :class:`~agents.tools.model.ModelPort`,
confined to a scoped subset of the platform toolset (capability confinement — a writer cannot run
shell tools).

The orchestration, deliberately legible (no framework hides when it delegates, parallelizes, or
halts):

1. **Plan** — decompose the task into :class:`SubTask`s (deterministically in MOCK; via the model
   on the live path).
2. **Route** — send each sub-task to the worker whose capabilities match.
3. **Run** — sequentially, or fan **independent** sub-tasks out in parallel and rejoin them, while
   respecting declared dependencies.
4. **Isolate failure** — a worker that crashes becomes a recorded failure, not a crash; the team
   *degrades*.
5. **Aggregate** — fold worker outputs into one answer.
6. **Decide done** — stop when every sub-task has a result (or a guard trips) and report *why*.

Two coordination guards keep a delegating system from melting down: an iteration cap (the planner
can't loop forever) and failure isolation (one bad worker degrades the team instead of aborting
it). They are small on purpose — the value of the pattern is that you can read exactly when and
why it halts.
"""

from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, Sequence, TypeVar

from .raw import AgentLoop, StopReason
from .tools.executors import default_toolset
from .tools.model import ModelPort, default_model
from .tools.schemas import ToolRegistry

T = TypeVar("T")


# =============================================================================================
# Coordination guards (Ch 17)
# =============================================================================================


class GuardTripped(RuntimeError):
    """Raised when an orchestration limit is exceeded. Carries the limit for logs."""

    def __init__(self, kind: str, limit: int) -> None:
        super().__init__(f"{kind} guard tripped (limit={limit})")
        self.kind = kind
        self.limit = limit


@dataclass
class IterationGuard:
    """Caps how many planning/delegation rounds the supervisor may run.

    ``tick()`` once per round; it raises :class:`GuardTripped` when the budget is spent — a runaway
    planner halts loudly rather than billing forever.
    """

    max_iterations: int = 8
    count: int = 0

    def tick(self) -> int:
        self.count += 1
        if self.count > self.max_iterations:
            raise GuardTripped("iteration", self.max_iterations)
        return self.count

    @property
    def remaining(self) -> int:
        return max(0, self.max_iterations - self.count)


@dataclass
class Outcome(Generic[T]):
    """The result of an isolated unit of work: either a value or a captured failure.

    A failed :class:`Outcome` is *data*, not an exception in flight, so the supervisor can look at
    ``ok`` across all workers and decide how to degrade.
    """

    ok: bool
    value: T | None = None
    error: str | None = None
    traceback_str: str | None = None

    @property
    def failed(self) -> bool:
        return not self.ok

    def unwrap(self) -> T:
        if not self.ok:
            raise RuntimeError(f"unwrap() on a failed Outcome: {self.error}")
        return self.value  # type: ignore[return-value]


def run_isolated(fn: Callable[[], T]) -> Outcome[T]:
    """Run ``fn`` and capture any exception as an :class:`Outcome` — the failure-isolation primitive."""
    try:
        return Outcome(ok=True, value=fn())
    except Exception as exc:  # noqa: BLE001 — isolation is the whole point here.
        return Outcome(
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            traceback_str=traceback.format_exc(),
        )


# =============================================================================================
# Sub-tasks, workers, routing
# =============================================================================================


@dataclass(frozen=True)
class SubTask:
    """One unit of work the supervisor delegates.

    ``depends_on`` references other sub-task ids; sub-tasks with no unmet dependency are
    independent and may run in parallel.
    """

    id: str
    description: str
    capability: str = ""
    depends_on: tuple[str, ...] = ()


@dataclass
class WorkerResult:
    """What a worker hands back to the supervisor."""

    worker: str
    role: str
    task: str
    output: str
    stop_reason: str = StopReason.COMPLETED.value
    turns: int = 0


@dataclass
class Worker:
    """A specialist: a name, a role, advertised capabilities, and a *confined* agent loop.

    The worker is a real :class:`~agents.raw.AgentLoop` over a *scoped* toolset — the supervisor
    cannot widen it at call time, which is what makes multi-agent delegation safe. ``capabilities``
    are free-form tags the router matches sub-tasks against.
    """

    name: str
    role: str
    agent: AgentLoop
    capabilities: frozenset[str] = field(default_factory=frozenset)
    system_prompt: str | None = None

    def can_handle(self, tags: frozenset[str]) -> bool:
        return bool(self.capabilities & tags)

    def run(self, task: str) -> WorkerResult:
        """Drive the worker's agent loop on ``task`` and package the result."""
        prompt = self.system_prompt or f"You are {self.name}, a {self.role} specialist."
        result = self.agent.run(task, system_prompt=prompt)
        return WorkerResult(
            worker=self.name,
            role=self.role,
            task=task,
            output=result.output,
            stop_reason=result.stop_reason.value,
            turns=result.turns,
        )

    def handle(self, task: str) -> Outcome[WorkerResult]:
        """Run the worker with failure isolation — the surface the supervisor calls."""
        return run_isolated(lambda: self.run(task))


class NoWorkerForTask(LookupError):
    """Raised when no worker advertises the required capability."""

    def __init__(self, subtask: SubTask) -> None:
        super().__init__(
            f"no worker can handle sub-task {subtask.id!r} (capability={subtask.capability!r})"
        )
        self.subtask = subtask


@dataclass
class KeywordRouter:
    """Deterministic capability-tag router — the safe default (free in MOCK, assertable in tests).

    Stage 1: direct capability match against each worker's advertised tags. Stage 2: scan the
    sub-task description tokens against worker capabilities. Ties break by worker order (stable).
    """

    workers: Sequence[Worker]

    def route(self, subtask: SubTask) -> Worker:
        tag = frozenset({subtask.capability}) if subtask.capability else frozenset()
        for worker in self.workers:
            if tag and worker.can_handle(tag):
                return worker
        tokens = frozenset(_words(subtask.description))
        best: Worker | None = None
        best_score = 0
        for worker in self.workers:
            score = len(worker.capabilities & tokens)
            if score > best_score:
                best, best_score = worker, score
        if best is not None:
            return best
        raise NoWorkerForTask(subtask)


def _words(text: str) -> list[str]:
    return [w for w in "".join(c.lower() if c.isalnum() else " " for c in text).split() if w]


# =============================================================================================
# Planning and aggregation
# =============================================================================================

Planner = Callable[[str], list[SubTask]]
Aggregator = Callable[[Sequence[Outcome[WorkerResult]]], str]


def default_planner(task: str) -> list[SubTask]:
    """Deterministic two-stage plan: research the task, then write it up.

    Mirrors the blueprint's researcher+writer demo. The writer depends on the researcher (they run
    sequentially); a task with two independent clauses (``" and "``) fans the research stage out in
    parallel.
    """
    clauses = [c.strip() for c in task.split(" and ") if c.strip()]
    if len(clauses) <= 1:
        research = [SubTask(id="research-1", description=f"Research: {task}", capability="research")]
    else:
        research = [
            SubTask(id=f"research-{i + 1}", description=f"Research: {clause}", capability="research")
            for i, clause in enumerate(clauses)
        ]
    write = SubTask(
        id="write-1",
        description=f"Write the final answer to: {task}",
        capability="write",
        depends_on=tuple(r.id for r in research),
    )
    return [*research, write]


def _successful(results: Sequence[Outcome[WorkerResult]]) -> list[WorkerResult]:
    return [o.value for o in results if o.ok and o.value is not None]


def last_writer_aggregate(results: Sequence[Outcome[WorkerResult]]) -> str:
    """Return the last successful output — the synthesis stage in a research→write pipeline."""
    ok = _successful(results)
    if not ok:
        return "No worker produced an answer."
    for r in reversed(ok):
        if any(k in r.role.lower() for k in ("writ", "edit", "summar")):
            return r.output
    return ok[-1].output


def concat_aggregate(results: Sequence[Outcome[WorkerResult]]) -> str:
    """Join each successful worker's output under a role header. Order-preserving."""
    parts = [f"## {r.role.capitalize()} ({r.worker})\n{r.output}" for r in _successful(results)]
    return "\n\n".join(parts) if parts else "No worker produced an answer."


@dataclass
class AggregateReport:
    """A structured view of a finished run — answer plus provenance and failures."""

    answer: str
    contributions: tuple[WorkerResult, ...]
    failures: tuple[str, ...]

    @property
    def degraded(self) -> bool:
        return bool(self.failures) and bool(self.contributions)


def build_report(results: Sequence[Outcome[WorkerResult]], answer: str) -> AggregateReport:
    ok = _successful(results)
    failures = tuple(o.error or "unknown error" for o in results if o.failed)
    return AggregateReport(answer=answer, contributions=tuple(ok), failures=failures)


# =============================================================================================
# The supervisor
# =============================================================================================


class DoneReason(str, Enum):
    """Why the supervisor stopped — asserted in tests, surfaced in the report."""

    COMPLETED = "completed"          # every sub-task produced a result
    DEGRADED = "degraded"            # finished, but one or more workers failed
    GUARD_TRIPPED = "guard_tripped"  # iteration cap hit before completion
    NO_PLAN = "no_plan"              # planner produced no sub-tasks


@dataclass
class RunResult:
    """Everything a supervised run produced: the answer, why it stopped, and full provenance."""

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

    Construct with :meth:`from_team` for the default config, or pass your own workers, planner,
    router, and aggregator. ``parallel=True`` fans independent sub-tasks out across a thread pool;
    dependent ones always wait for their inputs.
    """

    workers: Sequence[Worker]
    planner: Planner = default_planner
    aggregator: Aggregator = last_writer_aggregate
    parallel: bool = True
    max_workers: int = 4
    iteration_guard: IterationGuard = field(default_factory=lambda: IterationGuard(max_iterations=8))

    @classmethod
    def from_team(
        cls,
        *,
        model: ModelPort | None = None,
        tools: ToolRegistry | None = None,
        parallel: bool = True,
    ) -> "Supervisor":
        """Build the canonical researcher+writer team, each a confined :class:`~agents.raw.AgentLoop`."""
        model = model or default_model()
        toolset = tools or default_toolset()
        return cls(workers=default_team(model, toolset), parallel=parallel)

    def run(self, task: str) -> RunResult:
        router = KeywordRouter(self.workers)

        plan = self.planner(task)
        if not plan:
            empty = build_report([], "No plan could be formed for this task.")
            return RunResult(empty.answer, DoneReason.NO_PLAN, empty, (), 0)

        done: dict[str, Outcome[WorkerResult]] = {}
        ordered: list[Outcome[WorkerResult]] = []
        pending = list(plan)
        try:
            while pending:
                self.iteration_guard.tick()  # bound the orchestration rounds
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
        assignments: list[tuple[SubTask, Worker | _UnroutableWorker]] = []
        for st in ready:
            try:
                assignments.append((st, router.route(st)))
            except LookupError:
                assignments.append((st, _UnroutableWorker(st)))

        if not self.parallel or len(assignments) == 1:
            return [(st, worker.handle(st.description)) for st, worker in assignments]

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
            return DoneReason.DEGRADED if report.contributions else DoneReason.GUARD_TRIPPED
        return DoneReason.COMPLETED


@dataclass
class _UnroutableWorker:
    """Stand-in for a sub-task no real worker can handle — degrades the run like a crash would."""

    subtask: SubTask

    def handle(self, task: str) -> Outcome[WorkerResult]:
        return Outcome(
            ok=False,
            error=f"NoWorkerForTask: no worker for capability {self.subtask.capability!r}",
        )


def default_team(model: ModelPort, tools: ToolRegistry) -> list[Worker]:
    """The canonical 2-worker team: a researcher and a writer, each a *confined* agent loop.

    Each worker is a real :class:`~agents.raw.AgentLoop` over a scoped subset of the platform
    toolset — the researcher may search, the writer may not. That confinement (built with
    :meth:`ToolRegistry.subset`) is the safety property the supervisor pattern depends on.
    """
    researcher_tools = tools.subset({"search_docs", "clock", "calculator"})
    writer_tools = tools.subset({"clock"})
    researcher = Worker(
        name="researcher",
        role="research",
        agent=AgentLoop(model=model, tools=researcher_tools, max_turns=4),
        capabilities=frozenset({"research", "search", "investigate", "find", "facts"}),
        system_prompt="You are a meticulous research analyst. Gather and verify facts.",
    )
    writer = Worker(
        name="writer",
        role="writing",
        agent=AgentLoop(model=model, tools=writer_tools, max_turns=3),
        capabilities=frozenset({"write", "writing", "summarize", "draft", "explain", "report"}),
        system_prompt="You are a sharp technical writer. Turn findings into clear prose.",
    )
    return [researcher, writer]
