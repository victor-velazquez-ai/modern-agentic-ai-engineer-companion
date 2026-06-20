"""Multi-Agent Supervisor — a production-grade reference for orchestrating agents.

A supervisor plans and delegates to specialist workers, runs them sequentially or in
parallel, isolates worker failures, aggregates results, and decides when the job is
done. Each worker is an agent-loop with a scoped toolset and a role.

Quick start (runs offline, no API key, no spend)::

    from multi_agent_supervisor import Supervisor

    sup = Supervisor.from_team(mock=True)
    result = sup.run("Explain vector databases and write a short summary")
    print(result.reason)   # DoneReason.COMPLETED
    print(result.answer)

Composition note
----------------
In the full companion repo this pattern composes two sibling blueprints:

* ``../../agent-loop`` — each :class:`Worker` *is* an agent loop.
* ``../../llm-gateway`` — the supervisor's planning/routing/synthesis calls go through it.

Those are planned siblings; until they ship, :mod:`multi_agent_supervisor.model` carries
a deterministic mock and a thin live client so the pattern is fully runnable and tested
today. The :class:`~multi_agent_supervisor.model.ModelPort` Protocol is the seam a real
gateway client drops into with no upstream change.
"""

from __future__ import annotations

from .aggregate import (
    AggregateReport,
    ModelAggregate,
    build_report,
    concat_aggregate,
    last_writer_aggregate,
)
from .guards import (
    DepthGuard,
    GuardTripped,
    IterationGuard,
    Outcome,
    run_isolated,
)
from .model import (
    AnthropicModel,
    MockModel,
    ModelPort,
    ModelResponse,
    build_model,
    looks_like_injection,
    mock_enabled,
)
from .routing import (
    KeywordRouter,
    ModelRouter,
    NoWorkerForTask,
    SubTask,
)
from .supervisor import (
    DoneReason,
    RunResult,
    Supervisor,
    default_planner,
)
from .worker import (
    Tool,
    Worker,
    WorkerResult,
    default_team,
)

__all__ = [
    # supervisor
    "Supervisor",
    "RunResult",
    "DoneReason",
    "default_planner",
    # workers
    "Worker",
    "WorkerResult",
    "Tool",
    "default_team",
    # routing
    "SubTask",
    "KeywordRouter",
    "ModelRouter",
    "NoWorkerForTask",
    # aggregation
    "AggregateReport",
    "concat_aggregate",
    "last_writer_aggregate",
    "ModelAggregate",
    "build_report",
    # guards
    "IterationGuard",
    "DepthGuard",
    "Outcome",
    "GuardTripped",
    "run_isolated",
    # model port
    "ModelPort",
    "ModelResponse",
    "MockModel",
    "AnthropicModel",
    "build_model",
    "mock_enabled",
    "looks_like_injection",
]

__version__ = "0.1.0"
