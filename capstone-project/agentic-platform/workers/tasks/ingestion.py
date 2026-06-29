"""Document ingestion task: chunk → embed → index (Ch 13, 31).

When the API registers a document (``PENDING``), this task does the heavy ingestion off the hot
path and flips the catalog row to ``INDEXED`` (or ``FAILED``). The actual chunk/embed/index logic
lives in the ``rag/`` package (built in Ch 13); this task is the *worker wiring* around it — it
loads the catalog row, calls the ingest pipeline, and records the outcome.

In MOCK mode the ``rag`` pipeline is not invoked (it may not be built yet); the task simulates a
successful ingest deterministically so the worker path is exercisable offline.
"""

from __future__ import annotations

import logging

from celery import shared_task

from app.core.config import get_settings
from app.db.repositories import SqlAlchemyDocumentRepository
from app.domain.models import DocumentStatus
from workers.runtime import run_async, session_scope

log = logging.getLogger("agentic-platform.worker")


@shared_task(
    name="workers.tasks.ingestion.ingest_document",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    acks_late=True,
)
def ingest_document(self, document_id: str, tenant_id: str) -> dict[str, object]:
    """Ingest one registered document into the vector store and update its status."""

    async def _ingest() -> dict[str, object]:
        async with session_scope() as session:
            docs = SqlAlchemyDocumentRepository(session)
            document = await docs.get(tenant_id, document_id)
            if document is None:
                log.warning("ingest: document %s not found for tenant %s", document_id, tenant_id)
                return {"document_id": document_id, "status": "not_found"}

            # Idempotency: an already-indexed doc need not be re-ingested on redelivery.
            if document.status is DocumentStatus.INDEXED:
                return {"document_id": document_id, "status": document.status.value}

            chunk_count = await _run_ingest_pipeline(document.source_uri, tenant_id=tenant_id)

            document.status = DocumentStatus.INDEXED
            document.chunk_count = chunk_count
            await docs.add(document)  # upsert via the repository
            return {"document_id": document_id, "status": "indexed", "chunks": chunk_count}

    try:
        return run_async(_ingest())
    except Exception as exc:  # noqa: BLE001
        log.exception("ingest failed for %s: %s", document_id, exc)
        raise self.retry(exc=exc)


async def _run_ingest_pipeline(source_uri: str, *, tenant_id: str) -> int:
    """Call the ``rag/`` ingest pipeline, or simulate it in MOCK mode.

    ▢ TODO (live): replace the mock branch with the real pipeline once ``rag/`` lands::

        from rag.ingest import ingest_source
        return await ingest_source(source_uri, tenant_id=tenant_id)
    """
    settings = get_settings()
    if settings.is_mock:
        # Deterministic stand-in: a chunk count derived from the URI length, so tests are stable.
        return max(1, len(source_uri) % 7 + 1)

    # Lazy import so the worker compiles before rag/ exists.
    try:
        from rag.ingest import ingest_source  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on build order
        raise RuntimeError(
            "Live ingestion requested but the 'rag' package is not available. Build it (Ch 13) "
            "or run with COMPANION_MOCK=1."
        ) from exc
    return await ingest_source(source_uri, tenant_id=tenant_id)
