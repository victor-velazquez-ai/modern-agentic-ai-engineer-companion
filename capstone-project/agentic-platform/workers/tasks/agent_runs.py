"""Execute a queued agent run in the background, idempotently (Ch 29, 31).

The API enqueues a run (persisted ``QUEUED``); this task picks it up, drives it through the loop,
and persists the terminal state. It is the worker-side counterpart of ``RunService.run_inline``,
but resilient: bound with ``acks_late`` (see ``celery_app``) so a crash redelivers, and
**idempotent** so a redelivery does not double-execute a run that already reached a terminal
state.

The task body is synchronous (Celery), so it builds an async session + engine and bridges
through ``run_async``. Business logic stays in ``RunService`` — the task only wires and persists.
"""

from __future__ import annotations

import logging

from celery import shared_task

from app.db.repositories import SqlAlchemyRunRepository
from app.domain.models import RunStatus
from app.services.run_service import RunService
from workers.runtime import build_engine, run_async, session_scope

log = logging.getLogger("agentic-platform.worker")


@shared_task(
    name="workers.tasks.agent_runs.execute_run",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def execute_run(self, run_id: str, tenant_id: str) -> dict[str, str]:
    """Execute a previously-queued run to completion.

    Returns a small status dict for the result backend. Idempotent: if the run is already
    terminal (a redelivery), it returns immediately without re-running the agent.
    """

    async def _run() -> dict[str, str]:
        async with session_scope() as session:
            runs = SqlAlchemyRunRepository(session)
            run = await runs.get(tenant_id, run_id)
            if run is None:
                # Nothing to do — the row was deleted or never existed. Don't retry forever.
                log.warning("execute_run: run %s not found for tenant %s", run_id, tenant_id)
                return {"run_id": run_id, "status": "not_found"}

            # --- idempotency guard: never re-run a terminal run on redelivery ---
            if run.is_terminal:
                log.info("execute_run: run %s already %s; skipping", run_id, run.status.value)
                return {"run_id": run_id, "status": run.status.value}

            if run.status is RunStatus.QUEUED:
                run.transition_to(RunStatus.RUNNING)
                await runs.update(run)

            engine = build_engine()
            try:
                output = await engine.run(run.input, tenant_id=tenant_id)
                run.complete(output)
            except Exception as exc:  # noqa: BLE001 - persist failure, optionally retry
                run.fail(str(exc))
                await runs.update(run)
                raise
            await runs.update(run)
            return {"run_id": run_id, "status": run.status.value}

    try:
        return run_async(_run())
    except Exception as exc:  # noqa: BLE001
        # Retry transient failures with backoff; after max_retries the run stays FAILED.
        log.exception("execute_run failed for %s: %s", run_id, exc)
        raise self.retry(exc=exc)
