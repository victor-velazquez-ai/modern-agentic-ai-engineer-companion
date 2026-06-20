"""Layered memory for agents — working (short-term) + long-term, behind persistence.

This is the standalone, hardened version of the capstone ``memory/`` module (book Ch 14).
The public surface an agent uses is :class:`~memory_module.store.MemoryStore`; the layers it
composes are exported here for direct use and testing.

Design in one breath:

* **Working memory** (:mod:`memory_module.working`) is the live conversation window under a
  token budget. When it overflows, it does *not* silently truncate — it summarizes the oldest
  turns into a rolling summary and evicts them.
* **Long-term memory** (:mod:`memory_module.longterm`) holds durable facts/episodes and is read
  by relevance (a lexical score here; swap in embeddings for production).
* A **persistence backend** (:mod:`memory_module.backends`) makes both survive a restart. The
  in-process backend is the MOCK default; SQLite is the file-backed durability example.

Everything runs free and offline in ``MOCK=1`` (the default): the summarizer is a deterministic
extractive mock, so there is no API spend. See :mod:`memory_module.summarize` for how a live
``llm-gateway`` summarizer slots in.
"""

from __future__ import annotations

from .backends.base import PersistenceBackend
from .backends.memory import InMemoryBackend
from .backends.sqlite import SQLiteBackend
from .longterm import LongTermMemory, MemoryRecord
from .store import MemoryStore
from .summarize import MockSummarizer, Summarizer
from .working import Message, WorkingMemory

__all__ = [
    "InMemoryBackend",
    "LongTermMemory",
    "Message",
    "MemoryRecord",
    "MemoryStore",
    "MockSummarizer",
    "PersistenceBackend",
    "SQLiteBackend",
    "Summarizer",
    "WorkingMemory",
]

__version__ = "0.1.0"
