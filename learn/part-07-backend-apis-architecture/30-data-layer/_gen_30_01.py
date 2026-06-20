"""Generator for 30-01-postgres-modeling-indexing-transactions.ipynb.
Run once: python _gen_30_01.py ; then delete. Emits valid nbformat-4 JSON.
"""
import json, pathlib

def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text}

def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text}

cells = []

cells.append(md(
"""# Schema, indexes, transactions, migrations

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 30 §30.1, §30.3 · type: walkthrough*

**One-line promise:** model a `conversations`/`messages` schema, prove an index flips a full scan into an index seek, make two related writes all-or-nothing, and read a migration as a versioned, reversible change."""))

cells.append(md(
"""## 🧠 Why this matters

Agents reason; this is what they reason *over*. Conversation history, user data, retrieved knowledge, and tool results all live in a data layer, and a relational database is the sensible backbone. The relational guarantees you get almost for free — atomic transactions, foreign keys, constraints — are **correctness you don't have to engineer yourself**. The two levers that decide whether that layer flies or crawls are *indexing* (a query with no supporting index scans every row — fine at a thousand rows, catastrophic at ten million) and *transactions* (a group of writes that is all-or-nothing, so a crash can't leave half-applied state). Schema change is the third: never edit a production schema by hand — express every change as a reviewed, reversible **migration**."""))

cells.append(md(
"""## Objectives & prereqs

**By the end you can:**
- Model a normalized `conversations` / `messages` schema with a foreign key.
- Read a query plan and see an index turn a sequential scan into an index seek.
- Wrap two related writes in one transaction and prove a mid-way failure rolls *both* back.
- Read an Alembic-style up/down migration and say why it's reversible.
- Name when to reach past Postgres for a NoSQL access-pattern store — and when not to.

**Prereqs:** Ch 6 (data structures), Ch 29 (ACID vs distributed trade-offs). No API key, no model calls.

> ⚙️ **Runs free & offline.** Default backend is **SQLite in-memory** (stdlib `sqlite3`) so every cell — including `EXPLAIN` and the transaction demo — runs with **no containers**. The book targets PostgreSQL; where the plan output or SQL dialect differs, the cell says so. The optional live path (docker-compose Postgres) is documented at the end."""))

cells.append(code(
"""# --- Setup: imports, env, and the MOCK switch ---------------------------------
# Stdlib only. sqlite3 ships with Python; no pip install, no network, no key.
import os
import sqlite3
import random

try:
    from dotenv import load_dotenv  # from requirements.txt
    load_dotenv()
except ImportError:
    pass

# This notebook makes NO model calls, so MOCK only selects the *database backend*:
#   MOCK=1 (default): in-process SQLite — runs in CI, containerless, deterministic.
#   MOCK=0: connect to a real Postgres via DATABASE_URL (docker compose); the
#           EXPLAIN output and a few SQL features then match the book exactly.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"
random.seed(30)  # deterministic seed data

print(f"MOCK mode: {MOCK}  ->  backend: {'SQLite (in-memory)' if MOCK else 'PostgreSQL via DATABASE_URL'}")
if not MOCK and not os.getenv("DATABASE_URL"):
    raise SystemExit("MOCK=0 but DATABASE_URL is unset — start the compose Postgres or stay in mock mode.")

# One connection for the whole notebook (in-memory DB lives only as long as it does).
conn = sqlite3.connect(":memory:") if MOCK else None
if not MOCK:
    import psycopg  # from requirements.txt (psycopg[binary])
    conn = psycopg.connect(os.environ["DATABASE_URL"])
print("database connection ready")"""))

cells.append(md(
"""## 1 · Model the schema

Two tables: a `conversations` row per agent session, and many `messages` per conversation. The foreign key `messages.conversation_id → conversations.id` is a *constraint the database enforces* — you cannot insert a message for a conversation that doesn't exist, and (with `ON DELETE CASCADE`) deleting a conversation cleans up its messages. That referential integrity is correctness you'd otherwise hand-write and get wrong.

The DDL below is portable; the book's Postgres version uses `BIGSERIAL`/`TIMESTAMPTZ` where SQLite uses `INTEGER PRIMARY KEY`/`TEXT`. The *shape* is identical."""))

cells.append(code(
"""DDL = '''
CREATE TABLE conversations (
    id          INTEGER PRIMARY KEY,          -- Postgres: BIGSERIAL PRIMARY KEY
    user_id     INTEGER NOT NULL,
    created_at  TEXT    NOT NULL              -- Postgres: TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE messages (
    id               INTEGER PRIMARY KEY,
    conversation_id  INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role             TEXT    NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content          TEXT    NOT NULL,
    created_at       TEXT    NOT NULL
);
'''

cur = conn.cursor()
if MOCK:
    cur.execute("PRAGMA foreign_keys = ON")  # SQLite enforces FKs only when asked
cur.executescript(DDL) if MOCK else cur.execute(DDL)
conn.commit()
print("schema created: conversations, messages (FK + role CHECK constraint)")"""))

cells.append(md(
"""## 2 · Seed a few thousand rows (generated in-cell, not committed)

The standard is: tiny fixtures get committed; bulk data is *generated*. We synthesize ~200 conversations and a few thousand messages right here — enough that an index visibly changes the plan, small enough to run instantly."""))

cells.append(code(
"""N_CONV = 200
MSGS_PER_CONV = (8, 30)  # random range

def iso(day, sec):
    return f"2026-04-{day:02d}T{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"

conv_rows, msg_rows = [], []
mid = 1
for cid in range(1, N_CONV + 1):
    conv_rows.append((cid, random.randint(1, 50), iso(random.randint(1, 28), random.randint(0, 86399))))
    for _ in range(random.randint(*MSGS_PER_CONV)):
        role = random.choice(["user", "assistant"])
        msg_rows.append((mid, cid, role, f"message body {mid}", iso(random.randint(1, 28), random.randint(0, 86399))))
        mid += 1

cur.executemany("INSERT INTO conversations VALUES (?, ?, ?)" if MOCK
                else "INSERT INTO conversations VALUES (%s, %s, %s)", conv_rows)
cur.executemany("INSERT INTO messages VALUES (?, ?, ?, ?, ?)" if MOCK
                else "INSERT INTO messages VALUES (%s, %s, %s, %s, %s)", msg_rows)
conn.commit()
print(f"seeded {len(conv_rows)} conversations and {len(msg_rows)} messages")"""))

cells.append(md(
"""## 3 · 🔮 Predict: does the book's `messages` query scan or seek?

This is the hot query from §30.1 — fetch the most recent messages for one conversation:

```sql
SELECT * FROM messages
WHERE conversation_id = ?
ORDER BY created_at DESC
LIMIT 50;
```

There is **no index on `conversation_id` yet**. Before running the next cell: will the planner do a full table **scan** (read every message row) or an index **seek** (jump straight to the matching rows)? Why?"""))

cells.append(code(
"""HOT_QUERY = '''
SELECT * FROM messages
WHERE conversation_id = ?
ORDER BY created_at DESC
LIMIT 50
'''

def explain(sql, params):
    # SQLite: EXPLAIN QUERY PLAN gives a readable scan-vs-search summary.
    # Postgres: use EXPLAIN (its output names a Seq Scan vs Index Scan instead).
    if MOCK:
        rows = cur.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
        return "\\n".join(r[-1] for r in rows)
    cur.execute("EXPLAIN " + sql.replace("?", "%s"), params)
    return "\\n".join(r[0] for r in cur.fetchall())

print("PLAN without an index:")
print(explain(HOT_QUERY, (42,)))"""))

cells.append(md(
"""**What you just saw.** With no supporting index the plan is a **SCAN** of `messages` — the engine reads every row to find the ~dozen that match `conversation_id = 42`, then sorts them. At a few thousand rows it's instant; at ten million it is the difference between 2 ms and 2 seconds on your hottest path."""))

cells.append(md(
"""## 4 · Add the index from the book and re-read the plan

The book's index is **composite** — `(conversation_id, created_at)` — because the query both *filters* on `conversation_id` and *orders by* `created_at`. A composite index on both lets the engine seek to the conversation and walk rows already in `created_at` order, satisfying the `ORDER BY ... LIMIT` without a separate sort."""))

cells.append(code(
"""cur.execute(
    "CREATE INDEX idx_messages_conversation ON messages (conversation_id, created_at)"
)
conn.commit()

print("PLAN with idx_messages_conversation:")
print(explain(HOT_QUERY, (42,)))"""))

cells.append(md(
"""**What you just saw.** The plan flipped to a **SEARCH ... USING INDEX** (Postgres: *Index Scan*) — the engine jumps straight to the rows for conversation 42 instead of reading the whole table. You changed an algorithm, not a config flag, and you can *prove* it from the plan instead of guessing from wall-clock noise.

> 🎯 Reason from the **query plan**, not from a stopwatch. Wall-clock time is contaminated by cache state, other load, and warm-up; the plan tells you what the engine will actually do at scale."""))

cells.append(md(
"""## 5 · Transactions: two writes, all-or-nothing

Saving an agent turn is *two* related writes: record the user message **and** the assistant reply that answers it. If the process crashes between them, you must not be left with a user message and no answer (or a debit with no matching credit). Wrap both in one transaction so a failure rolls back *everything*.

🔮 **Predict:** we'll insert the user message, then raise an error *before* inserting the assistant message, all inside one transaction. After the rollback, how many of the two new rows survive — 0, 1, or 2?"""))

cells.append(code(
"""def count_msgs(cid):
    return cur.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = ?" if MOCK
                       else "SELECT COUNT(*) FROM messages WHERE conversation_id = %s", (cid,)).fetchone()[0]

CID = 1
before = count_msgs(CID)
next_id = cur.execute("SELECT MAX(id) FROM messages").fetchone()[0] + 1
ph = "(?, ?, ?, ?, ?)" if MOCK else "(%s, %s, %s, %s, %s)"

try:
    # Begin an explicit transaction (sqlite3 is in autocommit-ish mode by default).
    cur.execute("BEGIN")
    cur.execute("INSERT INTO messages VALUES " + ph,
                (next_id, CID, "user", "save this turn atomically", iso(28, 100)))
    # --- failure injected mid-transaction (e.g. the model call timed out) ---
    raise RuntimeError("assistant call failed before the reply was persisted")
    cur.execute("INSERT INTO messages VALUES " + ph,  # never reached
                (next_id + 1, CID, "assistant", "...", iso(28, 101)))
    conn.commit()
except RuntimeError as e:
    conn.rollback()
    print(f"rolled back: {e}")

after = count_msgs(CID)
print(f"messages for conversation {CID}: before={before}  after={after}  -> {after - before} new rows survived")"""))

cells.append(md(
"""**What you just saw.** `after == before` — **zero** new rows. The user message that *did* execute was undone by `rollback()` because it shared a transaction with the write that failed. That's the "A" in ACID: a group of changes is atomic — all of it lands or none of it does. No half-saved turns, ever."""))

cells.append(md(
"""## 6 · Migrations: schema change as a reviewed, reversible diff

You never `ALTER` a production schema by hand — you express the change as a **versioned migration** (Alembic in our stack). Each migration is a pair: `upgrade()` applies the change, `downgrade()` reverses it. Versioning keeps every environment in lock-step and makes a bad change a one-command rollback instead of a 2 a.m. incident.

Below is the *shape* of an Alembic revision adding a `model` column to `messages`. You don't need a live DB to read it — that's the point: it's auditable in code review."""))

cells.append(code(
"""ALEMBIC_REVISION = '''
\"\"\"add model column to messages

Revision ID: a1b2c3d4e5f6
Revises: 0f9e8d7c6b5a
\"\"\"
import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "0f9e8d7c6b5a"

def upgrade():
    # Nullable first so the migration is safe on a live table with existing rows.
    op.add_column("messages", sa.Column("model", sa.Text(), nullable=True))

def downgrade():
    op.drop_column("messages", "model")
'''
print(ALEMBIC_REVISION)

# We can demonstrate the *effect* of upgrade() on our SQLite DB (ALTER ... ADD COLUMN
# is one of the few ALTERs SQLite supports), then show downgrade is the inverse.
cur.execute("ALTER TABLE messages ADD COLUMN model TEXT")  # == upgrade()
cols = [r[1] for r in cur.execute("PRAGMA table_info(messages)").fetchall()]
print("\\nafter upgrade(), messages columns:", cols)
print("downgrade() would DROP that column — every change has a known inverse.")"""))

cells.append(md(
"""> ⚠️ **Pitfall — over-indexing.** An index is not free: every index must be **updated on every write** and it **costs disk**. Index a column you neither filter nor join on and you've bought slower inserts and a bigger database for zero read benefit. The rule from §30.6: *index what you filter and join on — and only those.* Adding `idx_messages_conversation` was justified because the hot query filters and orders by exactly those columns; a speculative index on `messages.content` would just tax every insert."""))

cells.append(code(
"""# Make the pitfall concrete: count how many indexes each write must now maintain.
idx = cur.execute(
    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='messages' AND name NOT LIKE 'sqlite_%'"
).fetchall()
print("explicit indexes on messages:", [r[0] for r in idx] or "(none)")
print("Every INSERT/UPDATE/DELETE on messages updates EACH of these. One earns its keep;")
print("a second on a column you never filter on would be pure write tax.")"""))

cells.append(md(
"""## 7 · NoSQL: a different mental model (not a faster Postgres)

Sometimes the relational model isn't the best fit and a NoSQL store earns its place. The shift is profound and worth stating plainly:

- **Relational (Postgres):** model the *data*, then write whatever queries you need later. A flexible query planner saves you.
- **NoSQL (DynamoDB especially):** model the *access patterns first*, then design the data to serve them. You must know how you'll read the data **before** you store it — there's no flexible planner to rescue you. Choosing the partition key and what to denormalize together *is* the design.

Reach for a DynamoDB-style store when you have a **known, high-scale access pattern** where its scale and operational simplicity clearly win:

| Pattern | Why NoSQL fits |
|---|---|
| Session store | One key (session id), pure get/put, enormous volume |
| High-write event log | Append-only, partition by time/source, no ad-hoc joins |
| Per-user timeline | Known read shape (by user id), denormalized for one fast query |

The practical default stands: **Postgres for flexibility**; choose NoSQL when a specific, high-scale pattern forces it — not reflexively."""))

cells.append(md(
"""## 🎯 Senior lens

**"Postgres until it hurts."** Distributed and NoSQL stores buy scale by *trading away* the relational guarantees — atomic transactions, foreign keys, constraints — and pushing that correctness burden back into your application code (Ch 29). That's a real, permanent tax. The senior move is to keep the ACID safety net until a concrete requirement — a measured scale ceiling, a latency SLO Postgres genuinely can't hit — forces the trade, and then to make it deliberately for that one access pattern, not to adopt an exotic store because it's fashionable. Index what you filter and join on; let the planner and the transaction log do the work you'd otherwise do by hand and get wrong."""))

cells.append(md(
"""## Recap

- A relational schema gives you **constraints the DB enforces** (FKs, CHECKs, atomic txns) — correctness you don't engineer yourself.
- An index changes the **query plan**: the hot `messages` query went from a full **scan** to an index **seek** with `(conversation_id, created_at)`. Read the plan, don't guess from wall-clock time.
- A **composite** index serves both the `WHERE` filter and the `ORDER BY`, avoiding a separate sort.
- A **transaction** makes related writes all-or-nothing — a mid-way failure rolled back *both* inserts, leaving zero half-applied state.
- **Migrations** (Alembic) are versioned, reviewed `upgrade()`/`downgrade()` pairs — never hand-edit a production schema.
- ⚠️ **Over-indexing** taxes every write; index only what you filter and join on.
- NoSQL means **model access patterns first** — choose it for a known high-scale pattern, not as a faster Postgres."""))

cells.append(md(
"""## Exercises

Predict before you run.

1. **Drop the index, re-explain.** `DROP INDEX idx_messages_conversation`, rerun the plan for the hot query, and confirm it reverts to a scan. Then recreate it. (Predict the plan string each time.)
2. **Index that doesn't help.** Add `CREATE INDEX idx_role ON messages(role)` and `EXPLAIN` the hot query again. Does the planner use it? Why not — and what did you just pay on every insert?
3. **Commit, not rollback.** Repeat the section-5 transaction but *remove* the injected `raise` and `commit()` both inserts. Predict `after - before`, then verify it's 2.
4. **CHECK constraint bites.** Try to insert a message with `role = 'tool'`. Predict the error before you run it, then read the message the `CHECK (role IN (...))` constraint produces."""))

cells.append(code("# Exercise 1 — your code here\n"))
cells.append(code("# Exercise 2 — your code here\n"))
cells.append(code("# Exercise 3 — your code here\n"))
cells.append(code("# Exercise 4 — your code here\n"))

cells.append(md(
"""## Next

- ➡️ **Next notebook:** [`30-02-sqlalchemy-pooling-and-the-n1-trap.ipynb`](./30-02-sqlalchemy-pooling-and-the-n1-trap.ipynb) — map these tables to SQLAlchemy objects and kill the N+1.
- 🔧 **Capstone:** this schema, its indexes, and the Alembic migrations seed `capstone/db/` — checkpoint `checkpoints/ch30-data-layer`.
- 🧩 **Blueprint:** the indexed `messages` retrieval shape feeds [`blueprints/rag-pipeline/`](../../../blueprints/rag-pipeline/)'s storage path.
- 🐳 **Live path (`MOCK=0`):** `docker compose up postgres`, set `DATABASE_URL=postgresql://...`, and rerun — the `EXPLAIN` then prints real Postgres plans (*Seq Scan* → *Index Scan*).
- See the book **§30.1** (indexing, transactions, migrations) and **§30.3** (NoSQL & access-pattern design)."""))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = pathlib.Path(__file__).parent / "30-01-postgres-modeling-indexing-transactions.ipynb"
out.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
print("wrote", out)
