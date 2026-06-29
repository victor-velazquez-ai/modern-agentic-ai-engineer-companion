"""Persistence backends for the memory subsystem.

A backend is the seam that makes memory survive a restart. The :class:`PersistenceBackend`
Protocol is the contract; two implementations ship:

* :class:`InMemoryBackend` — process-local, the ``MOCK`` default (durable only within one run).
* :class:`SQLiteBackend` — file-backed durability; the production swap (Postgres) is a drop-in at
  this same interface.

The same backend stores both per-session memory state (via :class:`~memory.store.MemoryStore`)
and run-level checkpoints (via :class:`~memory.checkpoint.CheckpointStore`), under distinct key
namespaces.
"""

from __future__ import annotations

from .base import PersistenceBackend, StoreState
from .memory import InMemoryBackend
from .sqlite import SQLiteBackend

__all__ = ["InMemoryBackend", "PersistenceBackend", "SQLiteBackend", "StoreState"]
