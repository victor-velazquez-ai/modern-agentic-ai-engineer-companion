"""In-process persistence backend — the ``MOCK`` default.

Stores session state and checkpoint blobs in plain dicts. It is durable *within a single process
run* (so the store's save/load logic, the long-term layer, and the checkpoint layer are all
exercised), but not across a real OS restart — that is what
:class:`~memory.backends.sqlite.SQLiteBackend` is for. We deep-copy on the way in and out so
callers can't mutate persisted state by reference (a subtle but real persistence bug).
"""

from __future__ import annotations

import copy
from typing import Any

from .base import StoreState


class InMemoryBackend:
    """Dict-backed persistence; zero dependencies, zero files, zero spend."""

    def __init__(self) -> None:
        self._data: dict[str, StoreState] = {}
        # namespace -> key -> blob, for run checkpoints and any other keyed JSON state.
        self._blobs: dict[str, dict[str, dict[str, Any]]] = {}

    # -- session memory state -------------------------------------------------------------------

    def save(self, session_id: str, state: StoreState) -> None:
        self._data[session_id] = copy.deepcopy(state)

    def load(self, session_id: str) -> StoreState | None:
        state = self._data.get(session_id)
        return copy.deepcopy(state) if state is not None else None

    def sessions(self) -> list[str]:
        return list(self._data.keys())

    # -- generic keyed blob store ---------------------------------------------------------------

    def save_blob(self, namespace: str, key: str, blob: dict[str, Any]) -> None:
        self._blobs.setdefault(namespace, {})[key] = copy.deepcopy(blob)

    def load_blob(self, namespace: str, key: str) -> dict[str, Any] | None:
        blob = self._blobs.get(namespace, {}).get(key)
        return copy.deepcopy(blob) if blob is not None else None

    def keys(self, namespace: str) -> list[str]:
        return list(self._blobs.get(namespace, {}).keys())

    def close(self) -> None:  # nothing to release
        return None
