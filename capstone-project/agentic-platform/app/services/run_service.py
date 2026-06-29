"""Run use-cases: create, fetch, list, and drive agent runs (Ch 25, 31).

This service is the story of an agent run. It depends only on *ports* — a ``RunRepository`` and
an ``AgentEngine`` — never on SQLAlchemy or a model SDK, so the same logic runs under a FastAPI
request and inside a Celery worker.

Two execution paths:

* **enqueue** (``create_run``) — persist a ``QUEUED`` run and hand it to the worker. The API
  stays thin; the long work happens in the background (Ch 31). The default path for real loads.
* **inline + stream** (``run_inline`` / ``stream_run``) — for short tasks and the SSE endpoint,
  execute against the engine right here and persist the terminal state. ``stream_run`` yields
  the engine's events through to the route, which serializes them as SSE frames.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from app.domain.errors import EntityNotFoundError
from app.domain.models import AgentRun, RunStatus
from app.domain.ports import AgentEngine, RunRepository
from app.services.agent_service import AgentRunEvent


class RunService:
    """Use-cases over :class:`~app.domain.models.AgentRun`."""

    def __init__(self, *, runs: RunRepository, engine: AgentEngine) -> None:
        self._runs = runs
        self._engine = engine

    async def create_run(
        self, *, tenant_id: str, task: str, metadata: dict | None = None
    ) -> AgentRun:
        """Persist a new ``QUEUED`` run (a worker will execute it). Returns the stored run."""
        run = AgentRun(tenant_id=tenant_id, input=task, metadata=metadata or {})
        return await self._runs.add(run)

    async def get_run(self, *, tenant_id: str, run_id: str) -> AgentRun:
        """Fetch one run for the tenant, or raise ``EntityNotFoundError``."""
        run = await self._runs.get(tenant_id, run_id)
        if run is None:
            raise EntityNotFoundError("AgentRun", run_id)
        return run

    async def list_runs(
        self, *, tenant_id: str, limit: int = 50, offset: int = 0
    ) -> Sequence[AgentRun]:
        """List the tenant's runs, newest first."""
        return await self._runs.list_for_tenant(tenant_id, limit=limit, offset=offset)

    async def run_inline(self, *, tenant_id: str, task: str) -> AgentRun:
        """Execute a run to completion *now* and persist the result.

        Used for short tasks and tests. Drives the run through its state machine
        (QUEUED → RUNNING → COMPLETED/FAILED) so the persisted record is always consistent.
        """
        run = await self.create_run(tenant_id=tenant_id, task=task)
        run.transition_to(RunStatus.RUNNING)
        await self._runs.update(run)
        try:
            output = await self._engine.run(task, tenant_id=tenant_id)
            run.complete(output)
        except Exception as exc:  # surface engine failures as a failed run, not a 500
            run.fail(str(exc))
            await self._runs.update(run)
            return run
        return await self._runs.update(run)

    async def stream_run(
        self, *, tenant_id: str, task: str, run_id: str | None = None
    ) -> AsyncIterator[AgentRunEvent]:
        """Stream an agent run's events, persisting the terminal state at the end.

        Yields the engine's ``start``/``token``/``end`` events straight through (the route turns
        each into an SSE frame). On completion the assembled output is saved; on error a
        terminal ``error`` event is emitted and the run is marked failed.
        """
        run = await self.get_run(tenant_id=tenant_id, run_id=run_id) if run_id else None
        if run is None:
            run = await self.create_run(tenant_id=tenant_id, task=task)
        # Only QUEUED runs can start; resuming a terminal run is a no-op error event.
        if run.status is not RunStatus.QUEUED:
            yield AgentRunEvent(
                type="error",
                data={"message": f"Run {run.id} is not startable (status={run.status.value})."},
            )
            return

        run.transition_to(RunStatus.RUNNING)
        await self._runs.update(run)

        chunks: list[str] = []
        try:
            async for event in self._engine.stream(task, tenant_id=tenant_id):
                if event.type == "token" and event.token:
                    chunks.append(event.token)
                yield event
            run.complete("".join(chunks))
            await self._runs.update(run)
        except Exception as exc:
            run.fail(str(exc))
            await self._runs.update(run)
            yield AgentRunEvent(type="error", data={"message": str(exc)})
