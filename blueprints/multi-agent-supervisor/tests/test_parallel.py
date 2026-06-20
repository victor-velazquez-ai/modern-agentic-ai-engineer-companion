"""Parallelism: independent sub-tasks fan out and rejoin correctly.

Covers the PLAN's `test_parallel.py` requirement. We assert three things:

1. Independent sub-tasks actually run concurrently (proven with a barrier, not luck).
2. Results rejoin in submission order regardless of finish order.
3. Dependent sub-tasks (writer-after-researcher) still run *after* their inputs.
"""

from __future__ import annotations

import threading
import time

from multi_agent_supervisor import (
    DoneReason,
    MockModel,
    SubTask,
    Supervisor,
    Worker,
    default_team,
)
from multi_agent_supervisor.routing import KeywordRouter


def _two_independent_research(task: str) -> list[SubTask]:
    """A plan with two independent research sub-tasks and no writer — pure fan-out."""
    return [
        SubTask(id="r1", description="Research alpha", capability="research"),
        SubTask(id="r2", description="Research beta", capability="research"),
    ]


def test_independent_subtasks_run_concurrently() -> None:
    # A barrier of size 2 only releases if both worker calls are in flight at once.
    barrier = threading.Barrier(2, timeout=5)

    class BarrierModel(MockModel):
        def complete(self, prompt, *, system=None, role=None):  # type: ignore[override]
            barrier.wait()  # raises BrokenBarrierError if the second call never comes
            return super().complete(prompt, system=system, role=role)

    model = BarrierModel()
    workers = [
        Worker(name="researcher", role="research", model=model, capabilities=frozenset({"research"})),
    ]
    sup = Supervisor(workers=workers, model=model, planner=_two_independent_research, parallel=True)
    result = sup.run("alpha and beta")
    # If they had run sequentially the barrier would have timed out and raised.
    assert result.ok
    assert len(result.report.contributions) == 2


def test_results_rejoin_in_submission_order() -> None:
    # r1 sleeps longer than r2, so r2 finishes first; the rejoin must still be r1, r2.
    class SkewModel(MockModel):
        def complete(self, prompt, *, system=None, role=None):  # type: ignore[override]
            if "alpha" in prompt:
                time.sleep(0.05)
            return super().complete(prompt, system=system, role=role)

    model = SkewModel()
    workers = [Worker(name="researcher", role="research", model=model, capabilities=frozenset({"research"}))]
    sup = Supervisor(workers=workers, model=model, planner=_two_independent_research, parallel=True)
    result = sup.run("alpha and beta")
    descriptions = [c.task for c in result.report.contributions]
    assert descriptions == ["Research alpha", "Research beta"]


def test_parallel_matches_sequential_results() -> None:
    # Same plan, parallel vs sequential, must produce the same set of worker outputs.
    model = MockModel()
    workers = default_team(model)
    par = Supervisor(workers=workers, model=model, planner=_two_independent_research, parallel=True).run("x and y")
    seq = Supervisor(workers=workers, model=model, planner=_two_independent_research, parallel=False).run("x and y")
    assert {c.output for c in par.report.contributions} == {c.output for c in seq.report.contributions}


def test_default_plan_fans_out_research_then_writes() -> None:
    # The default planner: "A and B" → two parallel research subtasks, then one writer
    # that depends on both. Proves dependent work waits for its inputs.
    sup = Supervisor.from_team(mock=True, parallel=True)
    result = sup.run("vector databases and embeddings")
    assert result.reason is DoneReason.COMPLETED
    # 2 research + 1 write = 3 sub-tasks planned.
    assert len(result.plan) == 3
    writer_subtask = [st for st in result.plan if st.id == "write-1"][0]
    assert set(writer_subtask.depends_on) == {"research-1", "research-2"}


def test_dependent_subtask_runs_after_dependency() -> None:
    # Record the order workers were invoked; the writer must come last.
    order: list[str] = []
    lock = threading.Lock()

    class TracingModel(MockModel):
        def complete(self, prompt, *, system=None, role=None):  # type: ignore[override]
            with lock:
                order.append(role or "?")
            return super().complete(prompt, system=system, role=role)

    model = TracingModel()
    sup = Supervisor(workers=default_team(model), model=model, parallel=True)
    sup.run("alpha and beta")
    assert order[-1] == "writing"  # the writer always runs after the researchers
    assert order.count("research") == 2


def test_router_used_within_a_wave_is_consistent() -> None:
    team = default_team(MockModel())
    router = KeywordRouter(team)
    wave = [
        SubTask(id="r1", description="Research alpha", capability="research"),
        SubTask(id="r2", description="Research beta", capability="research"),
    ]
    assert all(w.name == "researcher" for _, w in router.route_all(wave))
