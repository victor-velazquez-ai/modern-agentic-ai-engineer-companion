"""In-process persistence backend — the ``MOCK`` default.

Stores session state in a plain dict. It is durable *within a single process run* (so the store's
save/load logic and the long-term layer are exercised), but not across a real OS restart — that is
what :class:`~memory_module.backends.sqlite.SQLiteBackend` is for. We deep-copy on the way in and
out so callers can't mutate persisted state by reference (a subtle but real persistence bug).
"""

from __future__ import annotations

import copy

from .base import StoreState


class InMemoryBackend:
    """Dict-backed persistence; zero dependencies, zero files, zero spend."""

    def __init__(self) -> None:
        self._data: dict[str, StoreState] = {}

    def save(self, session_id: str, state: StoreState) -> None:
        self._data[session_id] = copy.deepcopy(state)

    def load(self, session_id: str) -> StoreState | None:
        state = self._data.get(session_id)
        return copy.deepcopy(state) if state is not None else None

    def sessions(self) -> list[str]:
        return list(self._data.keys())

    def close(self) -> None:  # nothing to release
        return None
