"""The Celery application — broker, result backend, and beat schedule (Ch 31).

One ``Celery`` instance the whole worker side shares. Broker and result backend both point at
Redis (``Settings.redis_url``); the beat schedule drives the periodic automations in
``tasks/schedules.py``. Tasks are auto-discovered from the ``workers.tasks`` package.

Run the worker and scheduler::

    uv run celery -A workers.celery_app worker --loglevel=info
    uv run celery -A workers.celery_app beat   --loglevel=info

Reliability defaults that matter (Ch 29, 31):

* ``task_acks_late=True`` + ``task_reject_on_worker_lost=True`` — a task is acknowledged only
  after it finishes, so a crashed worker's job is redelivered instead of lost.
* ``worker_prefetch_multiplier=1`` — long agent runs don't hog a queue; each worker pulls one
  at a time.
* ``task_track_started=True`` — runs surface a ``STARTED`` state for the run-status API.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "agentic_platform",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
    include=[
        "workers.tasks.agent_runs",
        "workers.tasks.ingestion",
        "workers.tasks.schedules",
        "workers.tasks.outbox",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Reliability (Ch 29): finish-then-ack so crashes redeliver, not drop.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    # A sane default ceiling so a stuck run can't pin a worker forever.
    task_time_limit=900,        # hard kill at 15 min
    task_soft_time_limit=840,   # soft (raises) at 14 min so the task can clean up
    result_expires=3600,
)

# Periodic automations (Ch 31). Beat enqueues these on the schedule below.
celery_app.conf.beat_schedule = {
    "relay-outbox-every-30s": {
        "task": "workers.tasks.outbox.relay_outbox",
        "schedule": 30.0,
    },
    "nightly-eval-sweep": {
        "task": "workers.tasks.schedules.nightly_eval_sweep",
        # 02:15 UTC daily — quiet hours.
        "schedule": crontab(hour=2, minute=15),
    },
    "reindex-stale-documents-hourly": {
        "task": "workers.tasks.schedules.reindex_stale_documents",
        "schedule": crontab(minute=0),
    },
}


__all__ = ["celery_app"]
