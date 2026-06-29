"""Background execution — Celery app, tasks, and schedules (Appendix C · ``workers/``).

The platform's key operational insight (Ch 31): **agent runs belong in the background.** The API
stays thin and *enqueues*; the worker does the long, retryable work and checkpoints its progress.
This package is the worker side of that split.

Layout (matches Appendix C)
---------------------------
``celery_app.py``       the Celery app + broker/result config + beat schedule (Ch 31).
``tasks/agent_runs.py`` execute a queued agent run end to end, idempotently (Ch 29, 31).
``tasks/ingestion.py``  chunk → embed → index a registered document (Ch 13, 31).
``tasks/schedules.py``  periodic automations driven by Celery beat (Ch 31).
``tasks/outbox.py``     the transactional-outbox relay + an idempotency-key guard (Ch 29).

The worker shares the backend's domain, services, and db code — one image, two entrypoints
(Appendix C's ``Dockerfile``). Everything is MOCK-runnable: with ``COMPANION_MOCK=1`` a task runs
the offline engine and never calls a model.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
