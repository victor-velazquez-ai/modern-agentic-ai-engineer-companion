"""Persistence backends for the memory module.

A backend is the seam that makes memory survive a restart. The :class:`PersistenceBackend`
Protocol is the contract; two implementations ship:

* :class:`InMemoryBackend` — process-local, the ``MOCK`` default (durable only within one run).
* :class:`SQLiteBackend` — file-backed durability; the production swap (Postgres) is a drop-in at
  this same interface.
"""

from __future__ import annotations

from .base import PersistenceBackend, StoreState
from .memory import InMemoryBackend
from .sqlite import SQLiteBackend

__all__ = ["InMemoryBackend", "PersistenceBackend", "SQLiteBackend", "StoreState"]
