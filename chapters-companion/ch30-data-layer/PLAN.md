# Ch 30 — Data Layer

> Companion plan · Part VII · book file `chapters/30-data-layer.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Agents reason; this is what they reason *over*. The notebooks turn the chapter's "Postgres
until it hurts" doctrine into muscle memory: the reader models a schema, watches an index turn
a full scan into an instant lookup, wraps writes in a transaction, kills an N+1, then caches
with Redis (including **LLM response caching**) and stores embeddings in `pgvector`. Real
services run via **docker compose**, but every notebook degrades to an in-process fake
(SQLite / a dict-backed Redis / a NumPy cosine search) so it runs free and green in CI with
no containers — the live path is documented and opt-in.

## Planned notebooks

### 30-01 · `30-01-postgres-modeling-indexing-transactions.ipynb` — Schema, indexes, transactions, migrations
- **Type:** walkthrough
- **Maps to:** §30.1 (PostgreSQL: indexing, transactions, migrations), §30.3 (NoSQL &
  access-pattern design — the relational-vs-access-pattern mental model)
- **Objective:** model a `conversations`/`messages` schema, prove an index changes the query
  plan, make a multi-write all-or-nothing in one transaction, and express a schema change as a
  reviewed migration — never by hand.
- **Prereqs:** Ch 6 (data structures), Ch 29 (ACID vs distributed trade-offs).
- **Cell arc:**
  - 🧠 the relational guarantees (atomic txns, FKs, constraints) = correctness you don't engineer.
  - Create the schema; seed a few thousand rows generated in-cell (not committed as a blob).
  - 🔮 *predict*: run the book's `messages` query with no index — scan or seek? Show
    `EXPLAIN` (full scan); add `idx_messages_conversation (conversation_id, created_at)`; rerun
    and read the plan flip to an index scan.
  - Transaction demo: two related writes; inject a failure mid-way; show rollback leaves no
    half-applied state (no debit without the matching credit).
  - Migrations: frame Alembic — a versioned, reviewed, reversible change; show an up/down pair
    conceptually (no live DB needed to read it).
  - NoSQL mental shift: model **data** (relational) vs model **access patterns first**
    (DynamoDB); when a known high-scale pattern (session store, event log, per-user timeline)
    earns a NoSQL store.
  - ⚠️ pitfall: over-indexing — each index slows writes and costs space; index what you filter
    and join on, and *only* those.
  - 🎯 senior lens: "Postgres until it hurts" — don't trade away ACID for scale until a real
    requirement forces it.
- **Datasets/fixtures:** schema DDL + an in-cell row generator; tiny `data/` seed optional.
- **APIs & cost:** none (no model calls). **Docker:** optional Postgres via compose; default
  falls back to **SQLite in-memory** so `EXPLAIN`/txn cells still run (note where plan output
  differs from real Postgres).
- **You'll be able to:** design an indexed, transactional schema and reason from a query plan
  instead of guessing.

### 30-02 · `30-02-sqlalchemy-pooling-and-the-n1-trap.ipynb` — ORM access patterns done right
- **Type:** walkthrough
- **Maps to:** §30.2 (ORMs, query builders, connection pooling)
- **Objective:** map rows to objects with SQLAlchemy, expose and fix the **N+1 query** with
  eager loading, and understand why a connection **pool** (and PgBouncer) keeps a burst from
  exhausting the database.
- **Prereqs:** 30-01.
- **Cell arc:**
  - Define SQLAlchemy models for `conversation` / `message`; note parameterized queries prevent
    SQL injection.
  - 🔮 *predict*: load 100 conversations then access each one's messages lazily — how many
    queries fire? Count them and watch **101**.
  - Fix with `selectinload`/`joinedload`; recount to **2**; emphasize watching the *query
    count* in traces, not just wall time.
  - Drop to raw SQL for one hot-path/reporting query to show the ORM leaks and that's fine.
  - Connection pooling: simulate a burst of concurrent "requests" against a small pool; show
    queueing vs exhaustion; explain PgBouncer in serverless / many-instance fleets.
  - ⚠️ pitfall: the N+1 is invisible in dev and a fire in prod — instrument the query count.
  - 🎯 senior lens: the ORM is a productivity tool that leaks; be fluent dropping to SQL on the
    hot path.
- **Datasets/fixtures:** reuse 30-01's schema/seed.
- **APIs & cost:** none. **Docker:** optional Postgres; defaults to SQLite. A query-logging
  hook counts statements so the N+1 lesson works on either backend.
- **You'll be able to:** spot and kill N+1s and size a connection pool for real concurrency.

### 30-03 · `30-03-redis-caching-and-vector-storage.ipynb` — Cache-aside, LLM response cache, and `pgvector`
- **Type:** walkthrough
- **Maps to:** §30.4 (caching with Redis; **LLM response caching**), §30.5 (search & vector
  storage: `pgvector` vs dedicated vector DB), §30.6 (operating the data layer)
- **Objective:** implement cache-aside with a TTL, extend it to cache **LLM completions** keyed
  by (model + inputs), store/query embeddings in `pgvector`, and weigh one-database simplicity
  against a dedicated vector store.
- **Prereqs:** 30-01; Ch 13 (RAG, embeddings) for the vector half.
- **Cell arc:**
  - 🧠 the fastest query is the one you never run; the **cache-aside** pattern (check → miss →
    fetch → backfill with TTL).
  - Implement the book's `get_profile` cache-aside; 🔮 *predict* hit vs miss latency, then show
    the second read served from cache.
  - **LLM response caching:** key an identical prompt (same model, same inputs) → return a
    cached completion; measure tokens/$ and latency saved; note semantic caching arrives in Ch 40.
  - `pgvector`: insert a handful of embeddings, run a top-k similarity query; contrast keeping
    vectors *in Postgres* (one backup, transactional consistency with the source rows) vs a
    dedicated Pinecone/Qdrant/Weaviate store at very large scale.
  - Operating the data layer: backups that are **tested by restoring**, read replicas (and
    replica lag ⇒ not for read-your-writes), and the data lifecycle (retain/archive/delete,
    right-to-be-forgotten).
  - ⚠️ pitfall: **cache invalidation** — prefer short TTLs + explicit invalidation on write;
    never cache what you can't afford to be briefly stale; ask "how wrong, for how long?"
  - 🎯 senior lens: **minimize the number of datastores** — every store is provision/secure/
    back-up/monitor/keep-consistent forever; make Postgres (`pgvector` + full-text) clear a
    high bar before adding one.
  - 📋 the chapter's data-layer checklist as a closing readiness cell.
- **Datasets/fixtures:** a few precomputed embedding vectors committed tiny; a canned LLM
  completion for the cache demo.
- **APIs & cost:** the LLM-cache cell is **mockable** (`MOCK=1` returns a canned completion so
  the hit/miss + cost-saving story runs free; `MOCK=0` does ~2 short live calls to populate the
  cache once). **Docker:** optional Redis + Postgres/pgvector via compose; defaults to a
  dict-backed fake Redis and a **NumPy cosine** vector search so everything runs containerless.
- **You'll be able to:** cache reads and LLM calls correctly and choose `pgvector` vs a
  dedicated vector DB on operational cost, not hype.

## Feeds (cross-pillar)
- **Blueprint(s):** caching + retrieval patterns inform
  [`blueprints/rag-pipeline/`](../../blueprints/rag-pipeline/) (the `pgvector` retrieval path)
  and the LLM-response-cache used by
  [`blueprints/llm/`](../../blueprints/llm/) and Ch 40's semantic cache.
- **Template(s):** the docker-compose data services (Postgres + Redis) feed the
  [`templates/fastapi-agent-service/`](../../templates/fastapi-agent-service/) compose file.
- **Capstone:** establishes `capstone-project/db/` (schema, Alembic migrations, SQLAlchemy models),
  `capstone-project/cache/` (Redis cache-aside + LLM cache), and the `pgvector` storage under
  `capstone-project/rag/`; checkpoint `checkpoints/ch30-data-layer`.

## Dependencies
- Ch 6 (data structures) · Ch 29 (ACID vs distributed consistency, replica lag, partition
  keys) · Ch 13 (embeddings/RAG, for the vector half). Precedes Ch 31 (workers persist
  state/checkpoints in this data layer) and Ch 40 (semantic caching builds on the LLM cache).

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` with **no containers** (SQLite / fake
  Redis / NumPy vectors) and with no errors; the live docker + `MOCK=0` path is documented.
- [ ] Index/`EXPLAIN`, transaction, N+1, cache-aside, and `pgvector` shapes match the book's
  §30 code and the closing checklist.
- [ ] Each ends with recap + exercises and links to `rag-pipeline`/`llm` blueprints and the
  capstone `db/`, `cache/`, `rag/` dirs.
- [ ] Secrets/DSNs from env only; no real connection strings or keys in committed outputs.
