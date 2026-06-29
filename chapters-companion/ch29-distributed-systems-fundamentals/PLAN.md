# Ch 29 — Distributed Systems Fundamentals

> Companion plan · Part VII · book file `chapters/29-distributed-systems-fundamentals.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This is the senior/architect core of Part VII — the deep CS a non-CS path skips, made
*runnable*. Every notebook is a **simulation**: partial failure, partitions, retries, and
multi-step consistency are reproduced **in-process** with mock services and an injectable
"network," so the reader *feels* the timeout-with-no-answer, watches a blind retry double a
charge, and then watches an idempotency key fix it — no real cluster, no cloud spend. The
goal is to convert the chapter's laws (CAP/PACELC, exactly-once-is-a-myth, sagas/outbox) from
words into instincts that later chapters and the capstone's workers depend on.

## Planned notebooks

### 29-01 · `29-01-partial-failure-and-cap-pacelc.ipynb` — The timeout with no answer, simulated
- **Type:** concept-lab
- **Maps to:** §29.1 (why distributed systems are hard: partial failure, no global clock),
  §29.2 (the eight fallacies), §29.3 (CAP, PACELC, consistency models)
- **Objective:** reproduce the three call outcomes (success / clean failure / **timeout with
  no answer**) against a flaky mock service, then force the CAP choice during a simulated
  partition and feel the PACELC latency↔consistency tax when there *isn't* one.
- **Prereqs:** Ch 4 (async), Ch 24 (request lifecycle, idempotency intro).
- **Cell arc:**
  - 🧠 two truths: partial failure and no global clock; why the third outcome is the heart of it.
  - A `flaky_call(p_fail, p_timeout)` mock that can return, raise, or hang→time out.
  - 🔮 *predict*: after a timeout, did the side effect happen? Run it and confront "you can't know."
  - The eight fallacies as a quick interactive table; tick which ones a given bug violated.
  - Simulate a two-node store with a toggleable *partition*: choose **CP** (refuse/stale-error)
    vs **AP** (serve stale, reconcile later) and observe what each returns mid-partition.
  - PACELC *else* branch: add coordination (a "quorum" round-trip) and measure the latency cost
    of stronger consistency when no partition exists.
  - ⚠️ pitfall: mis-stating CAP as "pick two of three" — partitions *will* happen; the choice
    is what to do *during* one.
  - 🎯 senior lens: the question is never "is it consistent?" but "*which* consistency does this
    feature need?" (chat history → read-your-writes; usage dashboard → eventual).
- **Datasets/fixtures:** none — all in-memory mock nodes and an injectable clock/network.
- **APIs & cost:** none — fully offline simulation (`time` is mocked; no real sleeps in CI).
- **You'll be able to:** name the three outcomes of any remote call and pick the consistency
  model a feature actually requires.

### 29-02 · `29-02-idempotency-retries-exactly-once-myth.ipynb` — Why a retry is safe only if you make it safe
- **Type:** concept-lab  *(carries the chapter's central correctness lesson)*
- **Maps to:** §29.6 (idempotency, retries, exactly-once myth); §29.8 (timeouts, retry with
  backoff + jitter, circuit breaker, bulkheads, backpressure — the failure-mode toolkit)
- **Objective:** show a blind retry double-charging a mock payment, fix it with a server-side
  **idempotency key**, then add backoff+jitter and a circuit breaker and watch a cascading
  failure get contained.
- **Prereqs:** 29-01.
- **Cell arc:**
  - Recreate the book's `charge(idempotency_key, ...)`: an in-memory ledger keyed by idem-key.
  - 🔮 *predict*: a client retries a timed-out charge with **no** key — how many debits land? Run
    it; see the double charge.
  - Add the idempotency key; replay the same retry; confirm "effectively once."
  - Spell out the proof: you can't distinguish a lost request from a lost response, so pick
    at-least-once + idempotent processing — "exactly-once delivery does not exist."
  - Retry policy lab: naive immediate retries → a synchronized **stampede**; add exponential
    backoff **+ jitter** and watch the thundering herd disperse.
  - Circuit breaker around a "sick" dependency: open after N failures, fail fast, half-open to
    probe recovery; bulkhead two pools so one saturated path can't starve the other;
    backpressure by rejecting when a bounded queue is full.
  - ⚠️ pitfall: the **cascading failure** — a slow dep makes callers pile up, exhausting
    threads/connections, taking down their callers; the toolkit exists to break this chain.
  - 🎯 senior lens: every model/tool call is a remote call that fails three ways — make every
    side-effecting tool idempotent, time-bounded, retried-with-backoff, and circuit-broken.
- **Datasets/fixtures:** in-memory ledger + a tunable flaky dependency; deterministic RNG seed
  for jitter so runs reproduce.
- **APIs & cost:** none — offline; the "payment gateway" and "LLM/tool" are mocks.
- **You'll be able to:** make any operation safe to retry and contain a failing dependency
  before it cascades.

### 29-03 · `29-03-outbox-and-sagas-simulated.ipynb` — Atomic state+event, and undoing across services
- **Type:** concept-lab
- **Maps to:** §29.5 (partitioning & replication, briefly), §29.7 (time/ordering, logical
  clocks, **transactional outbox**, **saga** with compensations)
- **Objective:** reproduce the dual-write problem (update DB *and* publish an event) and solve
  it two ways — a transactional outbox with an at-least-once relay + idempotent consumer, and a
  multi-step saga whose compensating actions roll back a partial failure.
- **Prereqs:** 29-02 (idempotency underpins both patterns).
- **Cell arc:**
  - 🧠 the dual-write trap: a crash *between* the DB write and the publish leaves them disagreeing.
  - 🔮 *predict*: inject a crash after the DB commit but before publish — is the event lost? Run it.
  - Outbox: write business row **and** an outbox row in *one* in-memory transaction; a relay
    loop reads the outbox and "publishes" at-least-once; an **idempotent consumer** absorbs the
    duplicates the relay's retries produce.
  - Logical-clock aside: order two events by version number, not wall clock, across mock nodes.
  - Saga: a 3-step booking (each step a local transaction) where step 3 fails; run the
    **compensations** in reverse to undo steps 2 and 1; contrast with a single transaction you
    can't have across services.
  - Replication/partitioning note: a hot-partition demo — a skewed key funnels traffic to one
    shard; show even vs skewed key distribution (ties to Ch 30's partition-key choice).
  - ⚠️ pitfall: a non-idempotent outbox consumer turns the relay's safe retries into duplicate
    side effects — the outbox needs an idempotent sink to be correct.
  - 🎯 senior lens: *delegate* consensus/coordination (etcd, ZooKeeper, DB transactions); don't
    hand-roll it — distributed consensus is a graveyard of data-corrupting bugs.
- **Datasets/fixtures:** in-memory DB, outbox table, broker list, and consumer — all dicts/lists.
- **APIs & cost:** none — fully offline simulation; crash points are injected flags.
- **You'll be able to:** keep state and events consistent via an outbox and coordinate a
  multi-step process with compensations — and know when to reach for a managed primitive.

## Feeds (cross-pillar)
- **Blueprint(s):** — (foundations chapter; the resilience patterns here are *applied* by
  [`blueprints/agent-loop/`](../../blueprints/agent-loop/) (retries/timeouts on tool calls)
  and the capstone workers, not packaged as a standalone blueprint).
- **Template(s):** —
- **Capstone:** the correctness substrate for `capstone-project/workers/` (idempotent, at-least-once
  Celery tasks in Ch 31) and any event-driven glue (outbox/saga); no new capstone dir of its
  own. Foreshadows the Part XI "architecting at scale" pass.

## Dependencies
- Ch 24 (request lifecycle, first idempotency intro) · Ch 4 (async). Directly feeds Ch 31
  (Celery `acks_late` ⇒ at-least-once ⇒ tasks must be idempotent) and Ch 30 (partition keys,
  replica lag / eventual consistency).

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1`, fully offline and deterministically
  (clock and network mocked; jitter RNG seeded).
- [ ] The `charge` idempotency shape, the outbox flow, and the saga/compensation terms match
  the book's §29 code and vocabulary exactly.
- [ ] Each ends with recap + exercises ("make this tool idempotent", "add a compensation") and
  forward links to Ch 31 workers and Part XI.
- [ ] No real network, no sleeps that slow CI, no secrets in outputs.
