"""Run checkpoints — snapshot a long-running agent's state so it can resume (Ch 14).

Working/long-term memory let an agent remember *within* and *across* sessions. Checkpoints add the
third durability axis the platform needs: **a single long-running agent run that can be paused and
resumed.** A worker (Ch 31) executing an agent run checkpoints after each step; if the process
crashes, is redeployed, or the run is *held for human approval* (Ch 20), a fresh worker reloads
the checkpoint by ``run_id`` and continues exactly where it stopped — without replaying side
effects or re-spending tokens.

A :class:`Checkpoint` captures three things:

* the :class:`~memory.backends.base.StoreState` (working window + long-term records),
* a small, JSON-able ``agent_state`` blob the caller owns (step index, pending tool calls,
  scratchpad — whatever the loop needs to resume), and
* lightweight metadata (``run_id``, monotonically increasing ``step``, ``status``, timestamp).

:class:`CheckpointStore` persists these through the same
:class:`~memory.backends.base.PersistenceBackend` the rest of memory uses (in-process MOCK by
default; SQLite/Postgres for real durability), under a dedicated key namespace so checkpoints and
session state never collide.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .backends.base import PersistenceBackend, StoreState
from .backends.memory import InMemoryBackend
from .store import MemoryStore

#: backend key namespace under which run checkpoints live.
CHECKPOINT_NAMESPACE = "run_checkpoints"


@dataclass(frozen=True)
class Checkpoint:
    """An immutable snapshot of a run's resumable state at one step."""

    run_id: str
    step: int
    memory: StoreState
    agent_state: dict[str, Any] = field(default_factory=dict)
    status: str = "running"  # running | paused | awaiting_approval | done | failed
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "step": self.step,
            "memory": self.memory,
            "agent_state": self.agent_state,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        return cls(
            run_id=data["run_id"],
            step=int(data.get("step", 0)),
            memory=data["memory"],
            agent_state=dict(data.get("agent_state", {})),
            status=data.get("status", "running"),
            created_at=data.get("created_at", time.time()),
        )


class CheckpointStore:
    """Persist/resume run checkpoints through a :class:`PersistenceBackend`.

    Args:
        backend: where checkpoints are stored. Defaults to the in-process
            :class:`~memory.backends.memory.InMemoryBackend` (MOCK); pass a
            :class:`~memory.backends.sqlite.SQLiteBackend` (or a Postgres backend) for durability
            across a real restart.

    Persistence policy: **last-write-wins per ``run_id``.** A run has exactly one current
    checkpoint; saving a later step overwrites the earlier one. (Keeping a full history is a
    backend choice — the blob store could key on ``f"{run_id}:{step}"`` — but resume only needs
    the latest, so the default keys on ``run_id`` to stay cheap.)
    """

    def __init__(self, backend: PersistenceBackend | None = None) -> None:
        self.backend: PersistenceBackend = backend or InMemoryBackend()

    def save(self, checkpoint: Checkpoint) -> None:
        """Persist ``checkpoint`` as the current state of its run."""
        self.backend.save_blob(CHECKPOINT_NAMESPACE, checkpoint.run_id, checkpoint.to_dict())

    def load(self, run_id: str) -> Checkpoint | None:
        """Return the latest checkpoint for ``run_id``, or ``None`` if the run is unknown."""
        blob = self.backend.load_blob(CHECKPOINT_NAMESPACE, run_id)
        return Checkpoint.from_dict(blob) if blob is not None else None

    def runs(self) -> list[str]:
        """List run ids that have a checkpoint."""
        return self.backend.keys(CHECKPOINT_NAMESPACE)

    # -- convenience: checkpoint straight from a live MemoryStore --------------------------------

    def checkpoint(
        self,
        run_id: str,
        store: MemoryStore,
        *,
        step: int,
        agent_state: dict[str, Any] | None = None,
        status: str = "running",
    ) -> Checkpoint:
        """Snapshot ``store``'s memory plus the caller's ``agent_state`` and persist it.

        Returns the :class:`Checkpoint` that was saved, so the worker can record its step/status.
        """
        cp = Checkpoint(
            run_id=run_id,
            step=step,
            memory=store.state(),
            agent_state=dict(agent_state or {}),
            status=status,
        )
        self.save(cp)
        return cp

    def resume(
        self,
        run_id: str,
        *,
        token_budget: int = 512,
        keep_last: int = 2,
    ) -> tuple[MemoryStore, Checkpoint] | None:
        """Rebuild a :class:`MemoryStore` from a run's latest checkpoint.

        Returns ``(store, checkpoint)`` with the memory layers restored to the checkpointed state,
        or ``None`` if there is no checkpoint for ``run_id``. The returned store uses a fresh
        in-process backend for *session* persistence (the checkpoint is the source of truth for
        resume); the caller reads ``checkpoint.agent_state`` and ``checkpoint.step`` to continue
        the loop. ``COMPANION_MOCK`` still governs the summarizer choice.
        """
        cp = self.load(run_id)
        if cp is None:
            return None
        store = MemoryStore(
            session_id=run_id,
            token_budget=token_budget,
            keep_last=keep_last,
        )
        store.restore(cp.memory)
        return store, cp
