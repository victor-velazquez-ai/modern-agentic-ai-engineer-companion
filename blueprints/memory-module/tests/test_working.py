"""Working-memory tests: overflow → **summarize**, not silent truncation."""

from __future__ import annotations

from memory_module.summarize import EchoSummarizer, MockSummarizer
from memory_module.working import Message, WorkingMemory, estimate_tokens


def test_estimate_tokens_monotonic() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("hi") >= 1
    assert estimate_tokens("a much longer sentence here") > estimate_tokens("short")


def test_under_budget_keeps_all_turns_verbatim() -> None:
    wm = WorkingMemory(token_budget=10_000, summarizer=MockSummarizer())
    wm.add("user", "first")
    wm.add("assistant", "second")
    wm.add("user", "third")
    assert [m.content for m in wm.messages] == ["first", "second", "third"]
    assert wm.rolling_summary == ""
    assert wm.compactions == 0


def test_overflow_compacts_instead_of_dropping() -> None:
    # Tiny budget + keep_last=1 forces compaction as soon as a few turns land.
    wm = WorkingMemory(token_budget=12, keep_last=1, summarizer=MockSummarizer())
    facts = [
        "The capital of France is Paris.",
        "The user prefers metric units.",
        "The deployment region is us-east-1.",
        "The on-call engineer is Ada.",
    ]
    for f in facts:
        wm.add("user", f)

    # It must have compacted (not silently truncated): a rolling summary exists...
    assert wm.compactions > 0
    assert wm.rolling_summary != ""
    # ...the live window honored keep_last (only the most recent turn is kept verbatim)...
    assert len(wm.messages) == 1
    # ...and the most recent turn is still present verbatim.
    assert wm.messages[-1].content == facts[-1]
    # Note: with keep_last=1 the kept turn + the rolling summary can themselves exceed a tiny
    # budget; that's the floor winning (see test_keep_last_floor_*). When the budget has room
    # for the floor, it IS respected — see test_budget_is_met_when_floor_fits below.


def test_budget_is_met_when_floor_fits() -> None:
    # A budget with comfortable headroom over keep_last: compaction must bring us back under it.
    wm = WorkingMemory(token_budget=60, keep_last=1, summarizer=MockSummarizer())
    for i in range(12):
        wm.add("user", f"message number {i} with a little extra padding text to add weight")
    assert wm.compactions > 0
    assert wm.used_tokens() <= wm.token_budget


def test_evicted_turn_enters_summary_not_the_void() -> None:
    # The compaction contract: at the moment a turn is evicted, its content is folded INTO the
    # rolling summary — not silently dropped. (The summary is a lossy, recency-biased compaction,
    # so over a long chat the *oldest* fragment can later be squeezed out; that's exactly why
    # important facts are promoted to long-term memory via memorize(). See test_persistence.)
    wm = WorkingMemory(token_budget=20, keep_last=1, summarizer=MockSummarizer())
    wm.add("user", "My name is Ada Lovelace.")
    # Add just enough weight to force the FIRST eviction, then inspect the summary immediately.
    wm.add("assistant", "Nice to meet you. Let's begin the design review of the payment flow now.")
    assert wm.compactions >= 1, "expected the heavy turn to push the window over budget"
    assert all(m.content != "My name is Ada Lovelace." for m in wm.messages)
    # The just-evicted user turn is now represented in the summary.
    assert "Ada" in wm.rolling_summary


def test_system_prompt_is_never_evicted() -> None:
    wm = WorkingMemory(token_budget=12, keep_last=1, summarizer=MockSummarizer())
    wm.add("system", "You are a terse assistant.")
    for i in range(8):
        wm.add("user", f"turn number {i} with some padding text")
    rendered = wm.render()
    assert rendered[0].role == "system"
    assert rendered[0].content == "You are a terse assistant."


def test_render_orders_system_summary_then_turns() -> None:
    wm = WorkingMemory(token_budget=12, keep_last=1, summarizer=EchoSummarizer())
    wm.add("system", "sys")
    for i in range(6):
        wm.add("user", f"a fairly long user message number {i}")
    rendered = wm.render()
    assert rendered[0].role == "system" and rendered[0].content == "sys"
    # second element is the summary line (also a system role), since compaction occurred
    assert rendered[1].role == "system"
    assert "Summary of earlier conversation" in rendered[1].content


def test_keep_last_floor_prevents_dropping_recent_turn() -> None:
    # Budget so small even one turn exceeds it; keep_last must still protect the latest turn.
    wm = WorkingMemory(token_budget=1, keep_last=2, summarizer=MockSummarizer())
    wm.add("user", "a reasonably long and unavoidable recent message")
    wm.add("user", "another reasonably long unavoidable recent message")
    # We refuse to drop below keep_last even though we're over budget.
    assert len(wm.messages) == 2


def test_message_roundtrip() -> None:
    m = Message("user", "hello")
    assert Message.from_dict(m.to_dict()) == m
