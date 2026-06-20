"""Generator for 30-02-sqlalchemy-pooling-and-the-n1-trap.ipynb."""
import json, pathlib

def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text}

def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text}

cells = []

cells.append(md(
"""# ORM access patterns done right: the N+1 trap & pooling

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 30 §30.2 · type: walkthrough*

**One-line promise:** map rows to objects with SQLAlchemy, *watch* a lazy access fire 101 queries, fix it down to 2 with eager loading, and see why a connection **pool** keeps a burst from exhausting the database."""))

cells.append(md(
"""## 🧠 Why this matters

You'll usually talk to Postgres through an **ORM** like SQLAlchemy: it maps rows to Python objects and writes the SQL for you, and its parameterized queries prevent SQL injection. But the ORM **leaks** — the convenience hides what the database actually does, and the classic leak is the **N+1 query**: you load 100 conversations, then lazily touch each one's messages, firing 101 queries where 2 would do. It's invisible in dev (fast on tiny data) and a performance fire in prod. The fix is to watch the *query count* in your traces, not just the response time — and to be fluent dropping to raw SQL on the hot path. The other essential is **connection pooling**: opening a connection is expensive and databases cap how many they allow, so a pool reuses a fixed set and a burst queues instead of exhausting the server."""))

cells.append(md(
"""## Objectives & prereqs

**By the end you can:**
- Define SQLAlchemy models for `Conversation` / `Message` and query them as objects.
- **Count** the queries a piece of ORM code fires (not just time it).
- Reproduce the **N+1** (101 queries) and fix it with `selectinload` (2 queries).
- Drop to raw SQL for a reporting query and know that's fine.
- Explain how a **connection pool** + PgBouncer absorb a concurrency burst.

**Prereqs:** notebook **30-01** (the schema). No API key, no model calls.

> ⚙️ **Runs free & offline.** Default backend is **SQLite in-memory** via SQLAlchemy; a query-logging hook counts statements, so the N+1 lesson works identically on SQLite or Postgres. The live docker path is documented at the end."""))

cells.append(code(
"""# --- Setup: imports, env, and the MOCK switch ---------------------------------
# SQLAlchemy + stdlib only (both in requirements.txt). No network, no key.
import os
import random
from contextlib import contextmanager

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from sqlalchemy import create_engine, event, ForeignKey, String, select, func, text
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, Session, selectinload,
)

# No model calls here, so MOCK only selects the engine URL:
#   MOCK=1 (default): in-memory SQLite — containerless, deterministic, CI-safe.
#   MOCK=0: real Postgres via DATABASE_URL (docker compose). The query COUNT lesson
#           is identical on either backend; only the dialect of the emitted SQL differs.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"
random.seed(30)

ENGINE_URL = "sqlite+pysqlite:///:memory:" if MOCK else os.environ.get("DATABASE_URL", "")
print(f"MOCK mode: {MOCK}  ->  engine: {'SQLite (in-memory)' if MOCK else ENGINE_URL}")
if not MOCK and not ENGINE_URL:
    raise SystemExit("MOCK=0 but DATABASE_URL is unset — start the compose Postgres or stay in mock mode.")

engine = create_engine(ENGINE_URL, echo=False)
print("engine ready")"""))

cells.append(md(
"""## 1 · A query counter (so we measure the right thing)

The whole N+1 lesson hinges on counting *statements*, not seconds. SQLAlchemy lets us hook every SQL execution; we wrap that in a small context manager so any block can report exactly how many queries it fired."""))

cells.append(code(
"""class QueryCounter:
    \"\"\"Counts SQL statements executed on an engine — the N+1 detector you'd
    wire into traces (OpenTelemetry spans, Ch 22) in production.\"\"\"
    def __init__(self, engine):
        self.engine = engine
        self.count = 0

    def _on_execute(self, *args, **kwargs):
        self.count += 1

    @contextmanager
    def measure(self):
        self.count = 0
        event.listen(self.engine, "before_cursor_execute", self._on_execute)
        try:
            yield self
        finally:
            event.remove(self.engine, "before_cursor_execute", self._on_execute)

counter = QueryCounter(engine)
print("query counter armed")"""))

cells.append(md(
"""## 2 · Define the SQLAlchemy models

These map 1:1 onto the `conversations` / `messages` tables from 30-01. The `relationship()` is what makes `conversation.messages` *look* like a Python list — and it's exactly that convenience that hides the N+1."""))

cells.append(code(
"""class Base(DeclarativeBase):
    pass

class Conversation(Base):
    __tablename__ = "conversations"
    id:       Mapped[int] = mapped_column(primary_key=True)
    user_id:  Mapped[int] = mapped_column()
    # Default loading is LAZY: messages are fetched on first access, per-conversation.
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")

class Message(Base):
    __tablename__ = "messages"
    id:              Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    role:            Mapped[str] = mapped_column(String(16))
    content:         Mapped[str] = mapped_column(String)
    conversation:    Mapped["Conversation"] = relationship(back_populates="messages")

Base.metadata.create_all(engine)
print("models mapped: Conversation, Message (relationship = lazy by default)")"""))

cells.append(code(
"""# Seed 100 conversations, a handful of messages each (generated, not committed).
with Session(engine) as s:
    mid = 1
    for cid in range(1, 101):
        conv = Conversation(id=cid, user_id=random.randint(1, 25))
        for _ in range(random.randint(3, 8)):
            conv.messages.append(Message(id=mid, conversation_id=cid,
                                         role=random.choice(["user", "assistant"]),
                                         content=f"body {mid}"))
            mid += 1
        s.add(conv)
    s.commit()
print(f"seeded 100 conversations, {mid - 1} messages")"""))

cells.append(md(
"""## 3 · 🔮 Predict: how many queries does this fire?

We load **100 conversations**, then loop over them and touch `conv.messages` (lazy). Before running: how many SQL statements hit the database — 1, 2, or 101? Write down your guess, then count."""))

cells.append(code(
"""def total_messages_lazy():
    with Session(engine) as s:
        convs = s.scalars(select(Conversation)).all()   # query #1: the 100 conversations
        total = 0
        for conv in convs:
            total += len(conv.messages)                  # one query EACH on first access
        return total

with counter.measure():
    total = total_messages_lazy()
print(f"messages counted: {total}")
print(f"SQL statements fired: {counter.count}   <-- the N+1")"""))

cells.append(md(
"""**What you just saw.** **101 queries**: one to load the conversations, then one *more* per conversation when you touched `.messages`. On 100 tiny rows it's a blink; on 10,000 conversations under real latency it's 10,001 round trips and a production incident. Crucially, **wall-clock time wouldn't have told you** — the count did."""))

cells.append(md(
"""> ⚠️ **Pitfall — the N+1 is invisible in dev.** Your laptop's DB is in-memory-fast and your seed data is tiny, so the page renders instantly and the code ships. In prod, each lazy access is a network round trip across the connection — and 101 of them serialize into a slow endpoint that *only* shows up under load. **Instrument the query count** (a span attribute, a test assertion) so the regression is caught the moment it lands, not in an incident."""))

cells.append(md(
"""## 4 · Fix it: eager-load with `selectinload`

`selectinload` tells SQLAlchemy to fetch *all* the messages for the loaded conversations in **one** extra query (a single `IN (...)` over the conversation ids), then stitch them onto the objects. Two queries total, regardless of how many conversations. `joinedload` is the sibling tool (one query with a JOIN) — `selectinload` is usually the better default for one-to-many because it avoids row multiplication.

🔮 **Predict:** with `selectinload`, how many statements — 2, 11, or 101?"""))

cells.append(code(
"""def total_messages_eager():
    with Session(engine) as s:
        stmt = select(Conversation).options(selectinload(Conversation.messages))
        convs = s.scalars(stmt).all()      # query #1: conversations
        total = sum(len(conv.messages) for conv in convs)  # messages already loaded
        return total                       # query #2 (the IN-list) happened during load

with counter.measure():
    total = total_messages_eager()
print(f"messages counted: {total}")
print(f"SQL statements fired: {counter.count}   <-- fixed: constant, not N+1")"""))

cells.append(md(
"""**What you just saw.** **2 queries** for the same result — and it stays 2 whether you have 100 conversations or 100,000. The lesson isn't "always eager-load"; it's **watch the query count** and reach for `selectinload`/`joinedload` when a lazy relationship is accessed in a loop."""))

cells.append(md(
"""## 5 · Drop to raw SQL on the hot path — and that's fine

The ORM is a productivity tool, not a religion. For a reporting/aggregation query, hand-written SQL is often clearer *and* faster than coaxing the ORM into the right plan. Being fluent dropping down is a feature, not a failure — the ORM **leaks**, so use the leak deliberately."""))

cells.append(code(
"""# "Top 5 busiest conversations" — a single aggregate the DB does best.
REPORT_SQL = text('''
    SELECT conversation_id, COUNT(*) AS n
    FROM messages
    GROUP BY conversation_id
    ORDER BY n DESC
    LIMIT 5
''')

with counter.measure(), Session(engine) as s:
    rows = s.execute(REPORT_SQL).all()
print("top conversations by message count:", [tuple(r) for r in rows])
print(f"SQL statements fired: {counter.count}   <-- one query; parameterize any user input with bound params")"""))

cells.append(md(
"""## 6 · Connection pooling: absorbing a burst

Opening a database connection is expensive (TCP + TLS + auth), and Postgres caps how many it allows (`max_connections`). A **pool** keeps a small set of connections open and hands them out: a burst of N concurrent requests against a pool of size P means up to P run at once and the rest **queue** (briefly) instead of each opening a fresh connection and exhausting the server.

We simulate this with a bounded semaphore standing in for the pool. 🔮 **Predict:** with a pool of 5 and a burst of 20 "requests", what's the maximum number *in flight at once* — 5 or 20?"""))

cells.append(code(
"""import threading, time

POOL_SIZE = 5
BURST = 20
pool = threading.Semaphore(POOL_SIZE)   # stands in for the engine's connection pool

in_flight = 0
max_in_flight = 0
lock = threading.Lock()

def handle_request(i):
    global in_flight, max_in_flight
    with pool:                          # acquire a 'connection' (blocks if pool is empty)
        with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        time.sleep(0.01)                # simulate a short query
        with lock:
            in_flight -= 1

threads = [threading.Thread(target=handle_request, args=(i,)) for i in range(BURST)]
for t in threads: t.start()
for t in threads: t.join()

print(f"burst={BURST}  pool_size={POOL_SIZE}  ->  max concurrent in flight: {max_in_flight}")
print("The pool CAPPED concurrency at the pool size; the other requests queued instead of")
print("opening new connections. Without a cap, 20 fresh connections could exhaust Postgres.")"""))

cells.append(md(
"""**What you just saw.** Never more than **5** in flight — the pool *bounded* concurrency; surplus requests waited for a connection to free up. In serverless or many-instance fleets the math compounds: 200 app instances × a 10-connection pool each = 2,000 connections, well past Postgres's limit. That's what **PgBouncer** is for — a pooler in front of Postgres that multiplexes thousands of client connections onto a small number of real ones, so your fleet can't DDoS its own database."""))

cells.append(md(
"""## 🎯 Senior lens

The ORM is a **productivity tool that leaks**, and a senior treats it as exactly that. You let it write the boring CRUD and the parameterized queries (free SQL-injection protection), but you stay fluent dropping to SQL on the hot path, and you **instrument the query count** so an N+1 is a failing test, not a 2 a.m. page. Sizing the pool is the same kind of judgment: too small and requests queue under load; too large and a fleet of instances exhausts Postgres's connection limit — which is why you reach for PgBouncer before you reach for a bigger database. Measure queries and connections, not just latency; both are the leading indicators latency lags behind."""))

cells.append(md(
"""## Recap

- A SQLAlchemy `relationship()` is **lazy by default** — convenient, and the source of the N+1.
- **Count statements, not seconds.** A query counter (or trace span) makes the N+1 visible.
- The N+1 fired **101** queries; `selectinload` cut it to **2**, and stays 2 at any scale.
- ⚠️ The N+1 is **invisible in dev** and a fire in prod — assert on the query count in tests.
- **Dropping to raw SQL** on a reporting/hot-path query is fine — the ORM leaks; use it deliberately (and keep user input in bound parameters).
- A **connection pool** caps concurrency so a burst **queues** instead of exhausting Postgres; **PgBouncer** does this for many-instance / serverless fleets."""))

cells.append(md(
"""## Exercises

Predict before you run.

1. **`joinedload` vs `selectinload`.** Swap `selectinload` for `joinedload` in section 4 and count the statements. Predict the new count (hint: one query with a JOIN) and note the row-multiplication trade-off for one-to-many.
2. **Make the N+1 worse.** In the lazy version, also touch `conv.messages[0].conversation` inside the loop. Predict how the count changes before running.
3. **Size the pool.** Re-run section 6 with `POOL_SIZE = 1` and then `POOL_SIZE = 20`. Predict `max_in_flight` for each, and reason about what `POOL_SIZE = BURST` costs a real Postgres.
4. **Assert no N+1.** Write a `with counter.measure(): ...; assert counter.count <= 2` around the eager loader — the test that would have caught the regression in CI."""))

cells.append(code("# Exercise 1 — your code here\n"))
cells.append(code("# Exercise 2 — your code here\n"))
cells.append(code("# Exercise 3 — your code here\n"))
cells.append(code("# Exercise 4 — your code here\n"))

cells.append(md(
"""## Next

- ⬅️ **Previous:** [`30-01-postgres-modeling-indexing-transactions.ipynb`](./30-01-postgres-modeling-indexing-transactions.ipynb).
- ➡️ **Next:** [`30-03-redis-caching-and-vector-storage.ipynb`](./30-03-redis-caching-and-vector-storage.ipynb) — cache reads, cache *LLM completions*, and store embeddings in `pgvector`.
- 🔧 **Capstone:** these SQLAlchemy models live in `capstone/db/` (with the eager-loading patterns) — checkpoint `checkpoints/ch30-data-layer`.
- 🐳 **Live path (`MOCK=0`):** `docker compose up postgres`, set `DATABASE_URL`, rerun. The query-count lesson is identical; set `create_engine(..., pool_size=..., max_overflow=...)` to experiment with the *real* pool.
- See the book **§30.2** (ORMs, query builders, connection pooling)."""))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = pathlib.Path(__file__).parent / "30-02-sqlalchemy-pooling-and-the-n1-trap.ipynb"
out.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
print("wrote", out)
