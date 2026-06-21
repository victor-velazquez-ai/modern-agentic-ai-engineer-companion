"""``memory`` — layered agent memory + checkpoint persistence (Appendix C · ``memory/``).

This is the capstone's *assembled* memory subsystem — the integrated counterpart to the
``memory-module`` blueprint. It is what lets a long-running agent keep state across **a turn, a
session, and a restart** without blowing the context window or the budget, and lets a worker
**checkpoint a run and resume it** after a crash or a pause-for-approval.

Layout (matches Appendix C; ``memory/`` is a single module directory)
--------------------------------------------------------------------
``working.py``     short-term: the live conversation window under a token budget, with
                   summarize-on-overflow compaction (never silent truncation).
``longterm.py``    long-term: durable facts/episodes, read by **relevance** (recency tiebreak).
``summarize.py``   the rolling-summary strategy folded into working memory; ``MockSummarizer``
                   offline, a gateway-backed summarizer live.
``store.py``       :class:`MemoryStore` — the four-verb facade an agent uses
                   (``remember`` / ``memorize`` / ``recall`` / ``context``) + save/load.
``checkpoint.py``  run-level checkpoints: snapshot the full memory state under a ``run_id`` so a
                   worker can resume a long/paused run exactly where it stopped.
``backends/``      persistence adapters behind one Protocol: in-memory (MOCK), SQLite (file), with
                   Postgres as the production swap at the same interface.

Everything runs free and offline in ``COMPANION_MOCK=1`` (the default): the summarizer is a
deterministic extractive mock, relevance is lexical, and the default backend is in-process — so a
fresh :class:`MemoryStore` needs no keys, no files, and no spend. Secrets are read from the
environment only.
"""

from __future__ import annotations

from .backends.base import PersistenceBackend, StoreState
from .backends.memory import InMemoryBackend
from .backends.sqlite import SQLiteBackend
from .checkpoint import Checkpoint, CheckpointStore
from .longterm import LongTermMemory, MemoryRecord
from .store import MemoryStore
from .summarize import EchoSummarizer, MockSummarizer, Summarizer, default_summarizer
from .working import Message, Role, WorkingMemory, estimate_tokens

__all__ = [
    # working memory
    "WorkingMemory",
    "Message",
    "Role",
    "estimate_tokens",
    # long-term memory
    "LongTermMemory",
    "MemoryRecord",
    # summarization
    "Summarizer",
    "MockSummarizer",
    "EchoSummarizer",
    "default_summarizer",
    # facade
    "MemoryStore",
    # checkpoints
    "Checkpoint",
    "CheckpointStore",
    # persistence
    "PersistenceBackend",
    "StoreState",
    "InMemoryBackend",
    "SQLiteBackend",
]

__version__ = "0.1.0"
