"""The persistence contract: one Protocol, keyed reads and writes.

A backend stores and reloads a *session*'s state — the working window plus the long-term records —
keyed by ``session_id``, and (for run checkpoints) arbitrary JSON-able blobs keyed by a string.
Keeping the surface this small is deliberate: it is the seam where you swap the in-process MOCK
store for SQLite, and SQLite for Postgres/Redis in production, with no change to
:class:`~memory.store.MemoryStore` or :class:`~memory.checkpoint.CheckpointStore` above it.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict, runtime_checkable


class StoreState(TypedDict):
    """The full persisted shape for one session's memory."""

    working: dict[str, Any]
    longterm: list[dict[str, Any]]


@runtime_checkable
class PersistenceBackend(Protocol):
    """Load/save the memory state for a session, durably, plus a small keyed blob store for
    run checkpoints.

    Implementations must round-trip :class:`StoreState` exactly: ``save`` then ``load`` (even after
    a process restart, for file/DB backends) returns equal state. ``load`` of an unknown session
    returns ``None`` so the store can start fresh. The ``*_blob`` methods are the generic
    key→JSON store the checkpoint layer uses; a backend gets them for free if it can persist a
    dict.
    """

    # -- session memory state -------------------------------------------------------------------

    def save(self, session_id: str, state: StoreState) -> None:
        """Persist ``state`` for ``session_id`` (overwriting any prior state)."""
        ...

    def load(self, session_id: str) -> StoreState | None:
        """Return the stored state for ``session_id``, or ``None`` if there is none."""
        ...

    def sessions(self) -> list[str]:
        """List known session ids (useful for admin/inspection)."""
        ...

    # -- generic keyed blob store (run checkpoints) ---------------------------------------------

    def save_blob(self, namespace: str, key: str, blob: dict[str, Any]) -> None:
        """Persist a JSON-able ``blob`` under ``(namespace, key)`` (overwriting any prior)."""
        ...

    def load_blob(self, namespace: str, key: str) -> dict[str, Any] | None:
        """Return the blob stored under ``(namespace, key)``, or ``None`` if there is none."""
        ...

    def keys(self, namespace: str) -> list[str]:
        """List known keys within ``namespace`` (e.g. all checkpointed run ids)."""
        ...

    def close(self) -> None:
        """Release any resources (connections, file handles). Idempotent."""
        ...
