"""The persistence contract: one Protocol, two reads, two writes.

A backend stores and reloads a *session*'s state — the working window plus the long-term records —
keyed by ``session_id``. Keeping the surface this small is deliberate: it is the seam where you
swap the in-process MOCK store for SQLite, and SQLite for Postgres/Redis in production, with no
change to :class:`~memory_module.store.MemoryStore` above it.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict, runtime_checkable


class StoreState(TypedDict):
    """The full persisted shape for one session."""

    working: dict[str, Any]
    longterm: list[dict[str, Any]]


@runtime_checkable
class PersistenceBackend(Protocol):
    """Load/save the memory state for a session, durably.

    Implementations must round-trip :class:`StoreState` exactly: ``save`` then ``load`` (even after
    a process restart, for file/DB backends) returns equal state. ``load`` of an unknown session
    returns ``None`` so the store can start fresh.
    """

    def save(self, session_id: str, state: StoreState) -> None:
        """Persist ``state`` for ``session_id`` (overwriting any prior state)."""
        ...

    def load(self, session_id: str) -> StoreState | None:
        """Return the stored state for ``session_id``, or ``None`` if there is none."""
        ...

    def sessions(self) -> list[str]:
        """List known session ids (useful for admin/inspection)."""
        ...

    def close(self) -> None:
        """Release any resources (connections, file handles). Idempotent."""
        ...
