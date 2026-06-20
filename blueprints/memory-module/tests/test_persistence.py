"""Persistence tests: memory state **survives a store reopen** (and a real file restart)."""

from __future__ import annotations

import pytest

from memory_module.backends.memory import InMemoryBackend
from memory_module.backends.sqlite import SQLiteBackend
from memory_module.store import MemoryStore


def _backends(tmp_path):
    """Both backends under test: in-process and file-backed SQLite."""
    yield InMemoryBackend()
    yield SQLiteBackend(tmp_path / "memory.sqlite")


def test_inmemory_backend_roundtrips_state() -> None:
    be = InMemoryBackend()
    state = {"working": {"messages": [{"role": "user", "content": "hi"}]}, "longterm": []}
    be.save("s1", state)  # type: ignore[arg-type]
    loaded = be.load("s1")
    assert loaded == state
    assert be.load("missing") is None
    assert be.sessions() == ["s1"]


def test_inmemory_backend_does_not_alias_state() -> None:
    be = InMemoryBackend()
    state = {"working": {"messages": []}, "longterm": []}
    be.save("s1", state)  # type: ignore[arg-type]
    state["working"]["messages"].append({"role": "user", "content": "leak"})  # mutate caller copy
    loaded = be.load("s1")
    assert loaded is not None
    assert loaded["working"]["messages"] == []  # backend kept its own deep copy


def test_sqlite_backend_persists_across_reopen(tmp_path) -> None:
    db = tmp_path / "mem.sqlite"
    state = {"working": {"rolling_summary": "earlier stuff"}, "longterm": [{"text": "x"}]}

    be = SQLiteBackend(db)
    be.save("s1", state)  # type: ignore[arg-type]
    be.close()

    # Reopen a brand-new connection to the same file — this is the real restart.
    reopened = SQLiteBackend(db)
    loaded = reopened.load("s1")
    reopened.close()
    assert loaded == state


@pytest.mark.parametrize("backend_kind", ["memory", "sqlite"])
def test_store_recalls_fact_after_restart(backend_kind: str, tmp_path) -> None:
    """The headline guarantee: a fact written in one store is recalled by a fresh store."""
    if backend_kind == "memory":
        backend = InMemoryBackend()
    else:
        backend = SQLiteBackend(tmp_path / "store.sqlite")

    # Session 1: learn a durable fact and some conversation, then persist + close.
    store = MemoryStore.open("user-42", backend, token_budget=40, keep_last=1)
    store.set_system("You are a helpful assistant.")
    store.remember("user", "By the way, my name is Ada and I love Kafka.")
    store.memorize("The user's name is Ada.", kind="fact", tags=("identity",))
    store.memorize("The user is interested in Kafka streaming.", kind="fact")
    store.save()

    # Simulate a process restart: a NEW store on the SAME backend/session.
    if backend_kind == "sqlite":
        backend.close()
        backend = SQLiteBackend(tmp_path / "store.sqlite")

    revived = MemoryStore.open("user-42", backend, token_budget=40, keep_last=1)
    hits = revived.recall("what is the user's name?", top_k=1)
    assert hits, "the fact should be recalled after restart"
    assert "Ada" in hits[0].text
    # the system prompt also survived
    assert any(m.role == "system" and "helpful assistant" in m.content for m in revived.context())
    revived.close()


def test_unknown_session_starts_empty() -> None:
    store = MemoryStore.open("never-seen", InMemoryBackend())
    assert store.recall("anything") == []
    assert store.load() is False  # nothing to restore


def test_working_summary_survives_restart(tmp_path) -> None:
    """A rolling summary produced by overflow is itself durable."""
    db = tmp_path / "summ.sqlite"
    backend = SQLiteBackend(db)
    store = MemoryStore.open("sess", backend, token_budget=12, keep_last=1)
    store.remember("user", "Remember that the launch date is March 3rd.")
    for chatter in ("noted", "okay", "understood", "moving on now", "continuing further"):
        store.remember("assistant", chatter)
    assert store.summary != ""  # compaction happened
    saved_summary = store.summary
    store.save()
    backend.close()

    revived = MemoryStore.open("sess", SQLiteBackend(db), token_budget=12, keep_last=1)
    assert revived.summary == saved_summary
    revived.close()
