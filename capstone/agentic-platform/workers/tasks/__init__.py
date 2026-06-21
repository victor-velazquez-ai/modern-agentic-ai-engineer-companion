"""Celery task modules (Ch 31).

Each module holds one family of background work, registered on the shared ``celery_app``:

``agent_runs``  execute a queued agent run end to end, idempotently.
``ingestion``   chunk → embed → index a registered document into the vector store.
``schedules``   periodic automations driven by Celery beat.
``outbox``      transactional-outbox relay + idempotency-key guard.

Tasks are *thin*: they translate a message into a call on the same domain services the API uses,
then persist the outcome. Business rules live in ``app/``; the worker just runs them off the hot
path. The bridge from Celery's synchronous task body to the app's async services is
``workers.runtime.run_async``.
"""

from __future__ import annotations

__all__: list[str] = []
