#!/usr/bin/env python3
"""Runnable demo: a chat that **recalls an earlier fact after a restart** — in MOCK mode.

Run it::

    python demo.py            # uses a temp SQLite file; deletes it on the way out
    COMPANION_MOCK=1 python demo.py   # explicit (this is already the default)

What it shows, end to end and with zero API spend:

1. **Session 1** — the agent learns a durable fact ("my name is Ada") and chats enough that the
   working window overflows and *summarizes* the oldest turns instead of dropping them.
2. The store is **saved and closed** — the process "ends."
3. **Session 2 (after restart)** — a brand-new store opens the same durable backend, and the agent
   **recalls the fact** it learned before, plus the rolling summary of the earlier chat.

This is the Ch 14 promise made concrete: state survives a turn, a session, and a restart.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Run straight from a clone: make ``src/`` importable without installing.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

# Windows consoles default to cp1252 and choke on box-drawing/emoji; force UTF-8 so the demo
# prints cleanly everywhere. (No-op where stdout is already UTF-8.)
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except (AttributeError, ValueError):
    pass

from memory_module import MemoryStore, SQLiteBackend  # noqa: E402

SESSION = "demo-user"


def banner(text: str) -> None:
    print(f"\n{'─' * 70}\n{text}\n{'─' * 70}")


def show_context(store: MemoryStore) -> None:
    print("  live window the model would receive:")
    for msg in store.context():
        content = msg.content if len(msg.content) <= 80 else msg.content[:77] + "…"
        print(f"    [{msg.role:9}] {content}")


def session_one(db_path: Path) -> None:
    banner("SESSION 1 — learn a fact, chat until the window overflows, then persist")
    store = MemoryStore.open(SESSION, SQLiteBackend(db_path), token_budget=48, keep_last=2)
    store.set_system("You are a concise engineering assistant.")

    # The user introduces themselves — we promote that to durable long-term memory.
    intro = "Hi! My name is Ada Lovelace and I'm building a payments service in Python."
    store.remember("user", intro)
    store.memorize("The user's name is Ada Lovelace.", kind="fact", tags=("identity",))
    store.memorize("The user is building a payments service in Python.", kind="fact", tags=("project",))
    print(f"  user said: {intro!r}")
    print("  → promoted 2 durable facts to long-term memory")

    # Now a stretch of back-and-forth that pushes the working window past its budget.
    chatter = [
        ("assistant", "Got it. What would you like to work on first?"),
        ("user", "Let's start with idempotency keys for the charge endpoint."),
        ("assistant", "Good call. Store the key with the request hash and a TTL."),
        ("user", "And we should add retry-safe webhooks after that."),
        ("assistant", "Agreed — dedupe webhook deliveries by event id."),
    ]
    for role, text in chatter:
        store.remember(role, text)

    print(f"\n  working-memory compactions triggered: {store.working.compactions}")
    if store.summary:
        print(f"  rolling summary of evicted turns:\n    {store.summary}")
    show_context(store)

    store.save()
    store.close()
    print("\n  state saved to disk and store closed (process 'ends' here).")


def session_two(db_path: Path) -> None:
    banner("SESSION 2 — fresh process, same backend: does it remember?")
    # A brand-new store, brand-new SQLite connection to the same file = a real restart.
    store = MemoryStore.open(SESSION, SQLiteBackend(db_path), token_budget=48, keep_last=2)

    question = "Wait — what was my name again, and what am I building?"
    print(f"  user asks: {question!r}")

    hits = store.recall(question, top_k=2)
    print("\n  recalled from long-term memory (by relevance):")
    for rec in hits:
        print(f"    • [{rec.kind}] {rec.text}")

    if store.summary:
        print(f"\n  and the rolling summary from last session survived too:\n    {store.summary}")

    # Assert the headline guarantee so the demo is self-checking.
    names = " ".join(r.text for r in hits)
    assert "Ada Lovelace" in names, "demo failed: the earlier fact was not recalled after restart"
    print("\n  ✅ The agent recalled a fact learned BEFORE the restart. Memory persisted.")
    store.close()


def main() -> int:
    mock = os.getenv("COMPANION_MOCK", "1") != "0"
    mode = "MOCK (offline, no API spend)" if mock else "LIVE"
    print(f"Memory-module demo · mode: {mode}")
    if not mock:
        print("  note: this demo never calls a model; MOCK only affects the summarizer choice.")

    # Use a throwaway file so we never pollute the repo (and *.sqlite is gitignored anyway).
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "memory_demo.sqlite"
        session_one(db_path)
        session_two(db_path)
    print("\nDone. Temp database cleaned up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
