"""Long-term memory tests: a relevance read returns the **right** episode."""

from __future__ import annotations

from memory_module.longterm import LongTermMemory, MemoryRecord


def _seed() -> LongTermMemory:
    ltm = LongTermMemory()
    ltm.add("The user's name is Ada Lovelace.", kind="fact", tags=("identity",))
    ltm.add("The user works on a payments service in Python.", kind="fact", tags=("project",))
    ltm.add("In the last session we debugged a Kafka consumer lag issue.", kind="episode")
    ltm.add("The preferred deployment region is us-east-1.", kind="fact", tags=("ops",))
    return ltm


def test_relevance_read_returns_the_right_record() -> None:
    ltm = _seed()
    hits = ltm.search("what is the user's name?", top_k=1)
    assert len(hits) == 1
    assert "Ada Lovelace" in hits[0].text


def test_relevance_orders_by_overlap() -> None:
    ltm = _seed()
    hits = ltm.search("which region do we deploy to", top_k=2)
    assert hits, "expected at least one relevant record"
    assert "us-east-1" in hits[0].text  # the region fact must rank first


def test_unrelated_query_returns_nothing_with_min_score() -> None:
    ltm = _seed()
    hits = ltm.search("photosynthesis in marine algae", min_score=0.0)
    # No token overlap → Jaccard 0 → filtered out by the strictly-greater-than-min_score rule.
    assert hits == []


def test_kind_filter_scopes_the_search() -> None:
    ltm = _seed()
    episodes = ltm.search("session debugging", kind="episode", top_k=5)
    assert episodes and all(r.kind == "episode" for r in episodes)
    facts = ltm.search("session debugging", kind="fact", top_k=5)
    assert all(r.kind == "fact" for r in facts)


def test_recency_read_is_newest_first() -> None:
    ltm = LongTermMemory()
    a = ltm.add("first")
    b = ltm.add("second")
    c = ltm.add("third")
    # created_at is wall-clock; assert via insertion if timestamps collide on fast machines.
    recent = ltm.recent(top_k=3)
    ids = {r.record_id for r in recent}
    assert ids == {a.record_id, b.record_id, c.record_id}
    assert recent[0].created_at >= recent[-1].created_at


def test_ids_are_stable_and_unique() -> None:
    ltm = LongTermMemory()
    r1 = ltm.add("alpha")
    r2 = ltm.add("beta")
    assert r1.record_id != r2.record_id
    assert r1.record_id == "ltm-000001"


def test_record_roundtrip() -> None:
    rec = MemoryRecord(text="x", kind="episode", tags=("a", "b"), record_id="ltm-000009")
    assert MemoryRecord.from_dict(rec.to_dict()) == rec


def test_snapshot_restore_preserves_records_and_counter() -> None:
    ltm = _seed()
    snap = ltm.snapshot()
    restored = LongTermMemory()
    restored.restore(snap)
    assert len(restored) == len(ltm)
    # the id counter must advance past restored ids so new adds don't collide
    new = restored.add("a brand new fact")
    assert new.record_id not in {r.record_id for r in ltm.records}
