"""Transactional outbox relay + idempotency-key guard (Ch 29).

Two reliability primitives the platform leans on, kept deliberately small and storage-agnostic:

* **Transactional outbox** — when a service must both commit a DB change *and* emit a side effect
  (enqueue a task, call a webhook), it writes an *outbox row* in the **same transaction** as the
  change. A relay (this ``relay_outbox`` task, run by beat) later delivers those rows and marks
  them sent. That removes the dual-write race: either both the change and the intent to deliver
  commit, or neither does.
* **Idempotency keys** — a guard that records a key the first time it is seen and rejects repeats,
  so an at-least-once delivery (a Celery redelivery, a retried webhook) executes its effect once.

This module provides an in-memory reference implementation of both (enough for tests and the
MOCK path) plus the relay task. ▢ TODO: back ``IdempotencyStore`` and the outbox with Postgres /
Redis for production (a unique index on the key; a ``status`` column on the outbox row).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

from celery import shared_task

log = logging.getLogger("agentic-platform.worker")


class IdempotencyStore:
    """A thread-safe first-write-wins guard. ``seen(key)`` is True only on repeats."""

    def __init__(self) -> None:
        self._keys: set[str] = set()
        self._lock = threading.Lock()

    def seen(self, key: str) -> bool:
        """Record ``key``; return False the first time it is seen, True on every repeat."""
        with self._lock:
            if key in self._keys:
                return True
            self._keys.add(key)
            return False


# Process-wide guard for the MOCK/in-memory path. Production swaps in a DB-backed store.
idempotency = IdempotencyStore()


@dataclass
class OutboxMessage:
    """One pending side effect, written in the same transaction as the state change."""

    topic: str
    payload: dict[str, object]
    key: str
    created_at: float = field(default_factory=time.time)
    delivered: bool = False


class InMemoryOutbox:
    """A minimal outbox: append messages, relay undelivered ones, mark them sent."""

    def __init__(self) -> None:
        self._messages: list[OutboxMessage] = []
        self._lock = threading.Lock()

    def add(self, message: OutboxMessage) -> None:
        with self._lock:
            self._messages.append(message)

    def pending(self) -> list[OutboxMessage]:
        with self._lock:
            return [m for m in self._messages if not m.delivered]

    def mark_delivered(self, key: str) -> None:
        with self._lock:
            for m in self._messages:
                if m.key == key:
                    m.delivered = True


# Process-wide outbox for the reference/MOCK path.
outbox = InMemoryOutbox()


def _deliver(message: OutboxMessage) -> None:
    """Deliver one outbox message exactly once (guarded by the idempotency store).

    ▢ TODO: dispatch by ``topic`` to the real sink — enqueue a Celery task, POST a webhook,
    publish to a stream. Here it just logs, which is enough to prove the relay loop.
    """
    if idempotency.seen(message.key):
        log.info("outbox: %s already delivered (key=%s); skipping", message.topic, message.key)
        return
    log.info("outbox: delivering %s (key=%s)", message.topic, message.key)


@shared_task(name="workers.tasks.outbox.relay_outbox")
def relay_outbox() -> dict[str, int]:
    """Beat-scheduled relay: deliver every undelivered outbox message, then mark it sent."""
    pending = outbox.pending()
    for message in pending:
        _deliver(message)
        outbox.mark_delivered(message.key)
    return {"relayed": len(pending)}
