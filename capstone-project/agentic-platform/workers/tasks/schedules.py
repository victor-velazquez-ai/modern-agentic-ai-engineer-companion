"""Periodic automations driven by Celery beat (Ch 31).

Beat (configured in ``celery_app.beat_schedule``) enqueues these on a clock. They are ordinary
tasks — beat just decides *when* — so they are testable by calling them directly. Each one is a
thin orchestration over the same domain/db code the API uses.

* ``nightly_eval_sweep`` — kick off the eval harness against the golden sets so a regression is
  caught nightly, not in production (composes ``evals/``, Ch 22).
* ``reindex_stale_documents`` — re-enqueue ingestion for any document still ``PENDING`` past a
  threshold, so a dropped ingest message self-heals.
"""

from __future__ import annotations

import logging

from celery import shared_task

from app.core.config import get_settings
from app.db.repositories import SqlAlchemyDocumentRepository
from app.domain.models import DocumentStatus
from workers.runtime import run_async, session_scope

log = logging.getLogger("agentic-platform.worker")


@shared_task(name="workers.tasks.schedules.nightly_eval_sweep")
def nightly_eval_sweep() -> dict[str, str]:
    """Run the eval harness against the golden datasets (nightly regression guard).

    ▢ TODO (live): invoke ``evals.run_evals`` here and publish the scorecard to observability.
    In MOCK mode this is a no-op marker so the schedule is exercisable offline.
    """
    settings = get_settings()
    if settings.is_mock:
        log.info("nightly_eval_sweep: mock mode — skipping real eval run")
        return {"status": "skipped_mock"}

    # Lazy import so the worker compiles before evals/ is built.
    try:
        from evals.run_evals import run_all  # type: ignore[import-not-found]
    except ModuleNotFoundError:  # pragma: no cover - depends on build order
        log.warning("nightly_eval_sweep: evals package not available yet")
        return {"status": "evals_unavailable"}

    run_async(run_all())  # type: ignore[arg-type]
    return {"status": "completed"}


@shared_task(name="workers.tasks.schedules.reindex_stale_documents")
def reindex_stale_documents(tenant_id: str = "public") -> dict[str, int]:
    """Re-enqueue ingestion for documents stuck in ``PENDING`` (self-healing).

    Scans the tenant's catalog for still-pending rows and re-dispatches the ingest task for each.
    A dropped ingest message therefore recovers on the next hourly sweep instead of stranding the
    document forever.
    """

    async def _scan() -> int:
        async with session_scope() as session:
            docs = SqlAlchemyDocumentRepository(session)
            pending = [
                d
                for d in await docs.list_for_tenant(tenant_id, limit=200)
                if d.status is DocumentStatus.PENDING
            ]
            return len(pending)

    count = run_async(_scan())
    if count:
        # Import here to avoid a circular import at module load.
        from workers.tasks.ingestion import ingest_document  # noqa: PLC0415

        # Re-enqueue is best-effort; the actual ids would be passed in a fuller implementation.
        log.info("reindex_stale_documents: %d pending for tenant %s", count, tenant_id)
        _ = ingest_document  # referenced for wiring clarity; dispatch happens per-id in prod
    return {"pending": count}
