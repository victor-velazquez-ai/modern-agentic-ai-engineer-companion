# -*- coding: utf-8 -*-
"""Generator for 29-03-outbox-and-sagas-simulated.ipynb (concept-lab)."""
import json, os

OUT = os.path.join(os.path.dirname(__file__), "..",
                   "29-03-outbox-and-sagas-simulated.ipynb")

def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(text)}

def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": _lines(text)}

def _lines(text):
    text = text.rstrip("\n")
    parts = text.split("\n")
    return [p + "\n" for p in parts[:-1]] + [parts[-1]]

cells = []

cells.append(md(r"""# Atomic state+event, and undoing across services

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 29 §29.5, §29.7 · type: concept-lab*

**One-line promise:** reproduce the **dual-write** problem (update the DB *and* publish an event) and solve it two ways — a **transactional outbox** with an at-least-once relay + idempotent consumer, and a multi-step **saga** whose compensating actions roll back a partial failure. All in-process dicts and lists; crash points are injectable flags."""))

cells.append(md(r"""## 🧠 Why this matters

Almost every backend eventually needs to change state **and** tell the rest of the world about it: write the order row *and* publish an `OrderPlaced` event so the warehouse, email, and analytics react. The trap is that these are **two systems** (your DB and your message broker) with **no shared transaction** — so a crash *between* the two writes leaves them disagreeing forever. The order exists but nobody was told, or the event fired for an order that rolled back.

You can't make a database commit and a broker publish atomic. So you stop trying, and instead make the *publish* derivable from a single local transaction — the **transactional outbox**. And when a *business process* spans several services that each commit independently, you give up the dream of one big transaction and use a **saga**: a sequence of local steps, each with a compensating "undo". Both patterns lean entirely on the idempotency you built in notebook 29-02. Everything here is offline and deterministic; crashes are just flags you flip."""))

cells.append(md(r"""## Objectives & prereqs

**By the end you can:**
- Reproduce the **dual-write** inconsistency by injecting a crash between a DB commit and an event publish.
- Build a **transactional outbox**: business row + outbox row in *one* transaction; an at-least-once **relay**; an **idempotent consumer** that absorbs the relay's duplicate deliveries.
- Order events by a **logical clock** (version number), not wall-clock time, across mock nodes.
- Run a 3-step **saga** where step 3 fails and the **compensations** unwind steps 2 and 1 in reverse.
- See a **hot-partition** skew and why the partition key choice matters (ties to Ch 30).

**Prereqs:** notebook **29-02** (idempotency underpins both the outbox consumer and saga retries). No API key — the "DB", "broker", and "consumer" are plain dicts and lists; crash points are flags."""))

cells.append(code(r'''# --- Setup: imports, env, and the MOCK switch ---------------------------------
# stdlib only (+ python-dotenv from requirements.txt). No network, no real I/O.
import os
import random
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MOCK = os.getenv("COMPANION_MOCK", "1") == "1"
random.seed(29)  # the hot-partition demo's key hashing reproduces exactly

print(f"MOCK mode: {MOCK}  | in-memory DB + broker + consumer, seed=29")''' ))

cells.append(md(r"""## 1 · The dual-write trap (§29.7)

The naive approach: commit the business change to the DB, then publish the event to the broker. Two separate systems, two separate writes — and **no transaction spans both**. If the process crashes in the gap, you're permanently inconsistent."""))

cells.append(code(r'''# Two independent systems with NO shared transaction.
class Database:
    def __init__(self): self.rows = {}
    def commit(self, key, value): self.rows[key] = value   # local, atomic

class Broker:
    def __init__(self): self.published = []
    def publish(self, event): self.published.append(event)  # a DIFFERENT system


def place_order_naive(db, broker, order_id, *, crash_after_commit=False):
    db.commit(order_id, {"status": "placed"})    # 1) DB write commits
    if crash_after_commit:
        raise SystemExit("process crashed before the publish")  # 2) ...crash here
    broker.publish({"type": "OrderPlaced", "order_id": order_id})  # 3) publish

print("dual-write model ready: a DB and a broker, with nothing tying their writes together")''' ))

cells.append(md(r"""## 2 · 🔮 Predict: crash after the commit — is the event lost?

We place an order but inject a crash **after** the DB commit and **before** the publish.

Before running: **what does each system hold afterward?** Does the order exist in the DB? Did the `OrderPlaced` event reach the broker? Are they consistent?"""))

cells.append(code(r'''db, broker = Database(), Broker()
try:
    place_order_naive(db, broker, "ORD-1", crash_after_commit=True)
except SystemExit as e:
    print("crash:", e)

print("DB rows      :", db.rows)            # the order IS here
print("broker events:", broker.published)   # ...but the event is NOT
print()
consistent = ("ORD-1" in db.rows) == any(
    e["order_id"] == "ORD-1" for e in broker.published)
print("DB and broker agree about ORD-1?", consistent,
      "  <- inconsistent: the order exists but no one was notified")''' ))

cells.append(md(r"""**What you just saw.** The order sits committed in the DB, but the `OrderPlaced` event never published — the warehouse never ships, the customer never gets an email. The two systems disagree permanently, and no amount of retrying the *publish* helps, because after the crash there's nothing left in memory that *remembers a publish was owed*. That missing memory is exactly what the outbox restores."""))

cells.append(md(r"""## 3 · The transactional outbox (§29.7)

The fix: write the business row **and** an *outbox row* (the event-to-publish) in the **same local transaction**. Now they can't disagree — either both commit or neither does. A separate **relay** loop later reads unpublished outbox rows and publishes them to the broker, marking each done. Because the relay can crash and re-run, it delivers **at-least-once** — so the consumer must be **idempotent** (the 29-02 lesson)."""))

cells.append(code(r'''class OutboxDB:
    """One DB holding both business rows and an outbox table. A single transaction
    writes to BOTH, so the business change and the event-to-publish are atomic."""
    def __init__(self):
        self.rows = {}
        self.outbox = []   # each: {"id", "event", "published": bool}
        self._next = 0

    def place_order(self, order_id):
        # --- BEGIN single local transaction ---
        self.rows[order_id] = {"status": "placed"}            # business row
        self.outbox.append({"id": self._next,
                            "event": {"type": "OrderPlaced", "order_id": order_id},
                            "published": False})              # outbox row, SAME txn
        self._next += 1
        # --- COMMIT: both rows land together, or neither does ---


def relay(db, broker, *, deliver_twice=False):
    """Reads unpublished outbox rows and publishes them. At-least-once: a crash
    between 'publish' and 'mark published' re-delivers — modeled by deliver_twice."""
    for row in db.outbox:
        if row["published"]:
            continue
        broker.publish(row["event"])              # publish to the broker
        if deliver_twice:
            broker.publish(row["event"])          # crash-before-mark -> duplicate!
        row["published"] = True                   # mark done (may be lost on crash)


odb, broker = OutboxDB(), Broker()
odb.place_order("ORD-1")
print("after place_order -> rows:", odb.rows)
print("                     outbox:", odb.outbox)
relay(odb, broker, deliver_twice=True)            # relay re-delivers once
print("broker received:", [e["order_id"] for e in broker.published],
      "<- DUPLICATE: at-least-once delivery in action")''' ))

cells.append(md(r"""**What you just saw.** The order row and the outbox row committed **together** — survive a crash now and the relay will still find the pending event and publish it. But the relay delivered the event **twice** (it crashed after publishing, before marking the row done, so it re-published on restart). At-least-once delivery is the price of never *losing* an event. Which means the consumer must dedupe."""))

cells.append(md(r"""> ⚠️ **Pitfall — a non-idempotent outbox consumer.** The outbox guarantees *at-least-once*, so duplicates are **normal**, not exceptional. A consumer that isn't idempotent turns the relay's *safe* retries into *duplicate side effects* — two shipping labels, two emails. The outbox is only correct when paired with an **idempotent sink**. Below, the consumer dedupes on the event id."""))

cells.append(code(r'''class IdempotentConsumer:
    """Absorbs the duplicates at-least-once delivery produces, keyed on event id."""
    def __init__(self):
        self.processed = set()     # event keys already handled
        self.side_effects = []     # the real work (e.g. 'create shipment')

    def handle(self, event):
        key = (event["type"], event["order_id"])
        if key in self.processed:
            return "duplicate ignored"           # the 29-02 idempotency pattern
        self.processed.add(key)
        self.side_effects.append(f"shipped {event['order_id']}")
        return "processed"

consumer = IdempotentConsumer()
results = [consumer.handle(e) for e in broker.published]   # broker held 2 copies
print("per-event results:", results)
print("real side effects :", consumer.side_effects)
assert len(consumer.side_effects) == 1, "idempotent consumer must collapse duplicates"
print("Two deliveries, ONE shipment — the outbox + idempotent consumer is correct.")''' ))

cells.append(md(r"""**What you just saw.** The broker handed the consumer two copies of `OrderPlaced`; the consumer processed the first and **ignored** the second, yielding exactly one shipment. Outbox (never lose an event) + idempotent consumer (never act on it twice) = the reliable "state and event stay consistent" guarantee."""))

cells.append(md(r"""## 4 · Logical clocks: order by version, not wall time (§29.7)

With no global clock, two nodes' wall-clock timestamps can't be trusted to order events — clocks drift, and "later" is ambiguous. A **logical clock** (here, a monotonically increasing version number stamped by the owning node) gives a reliable order without trusting anyone's wall time."""))

cells.append(code(r'''@dataclass(order=True)
class Stamped:
    version: int            # logical clock — compare THIS, not wall time
    node: str = field(compare=False)
    payload: str = field(compare=False)

# Two nodes emit events; their wall clocks disagree, but versions are authoritative.
events = [
    Stamped(version=2, node="A", payload="balance=250"),
    Stamped(version=1, node="A", payload="balance=100"),
    Stamped(version=3, node="B", payload="balance=250 confirmed"),
]
ordered = sorted(events)    # sorts by version, the logical clock
print("correct causal order (by version, NOT wall clock):")
for e in ordered:
    print(f"  v{e.version}  [{e.node}]  {e.payload}")
print()
print("Latest authoritative value:", ordered[-1].payload,
      "- chosen by highest version, immune to clock drift")''' ))

cells.append(md(r"""**What you just saw.** Sorting by **version** recovered the true order — `v1 → v2 → v3` — regardless of what any machine's wall clock claimed. This is how replicas decide "which write wins" (last-writer-wins by version) and how event logs stay ordered across nodes that don't share a clock."""))

cells.append(md(r"""## 5 · Sagas: undoing across services (§29.7)

When a business process spans **multiple services** that each own their own transaction, you *cannot* wrap them in one ACID transaction. The **saga** pattern instead runs a sequence of local steps, and if a later step fails, it executes each completed step's **compensating action** in reverse — a semantic "undo".

We book a trip: **(1) reserve flight → (2) reserve hotel → (3) charge card.** Step 3 fails. Watch the compensations unwind the hotel and the flight."""))

cells.append(code(r'''@dataclass
class Step:
    name: str
    action: callable        # do the local transaction
    compensate: callable    # semantic undo if a later step fails

# Each service's tiny state.
state = {"flight": None, "hotel": None, "charge": None}
events_log = []

def run_saga(steps):
    done = []               # completed steps, for reverse compensation
    try:
        for step in steps:
            step.action()
            events_log.append(f"DID    {step.name}")
            done.append(step)
        return "saga committed"
    except Exception as e:
        events_log.append(f"FAIL   {step.name}: {e}")
        for step in reversed(done):           # compensate in REVERSE order
            step.compensate()
            events_log.append(f"UNDO   {step.name}")
        return f"saga rolled back ({e})"

def reserve_flight():  state["flight"] = "RESERVED"
def cancel_flight():   state["flight"] = "CANCELLED"
def reserve_hotel():   state["hotel"] = "RESERVED"
def cancel_hotel():    state["hotel"] = "CANCELLED"
def charge_card():     raise RuntimeError("card declined")   # step 3 fails
def refund_card():     state["charge"] = "REFUNDED"

saga = [
    Step("reserve_flight", reserve_flight, cancel_flight),
    Step("reserve_hotel",  reserve_hotel,  cancel_hotel),
    Step("charge_card",    charge_card,    refund_card),
]
outcome = run_saga(saga)
print("outcome:", outcome)
print("final state:", state)
print("\ntimeline:")
for line in events_log:
    print(" ", line)''' ))

cells.append(md(r"""**What you just saw.** Steps 1 and 2 committed (flight + hotel reserved); step 3 failed (card declined); the saga then ran the compensations **in reverse** — cancelling the hotel, then the flight — leaving the world consistent again. Note the compensations are *semantic* undos, not a rollback: a "cancel" is itself a real operation that should be **idempotent** (29-02), because the saga coordinator may retry it after a crash. Contrast this with a single DB transaction you simply *can't* have across three services."""))

cells.append(md(r"""## 6 · Partitioning & the hot-partition pitfall (§29.5)

A quick replication/partitioning note that ties forward to Ch 30. **Partitioning** (sharding) splits data across nodes by a key. The whole scheme lives or dies by **even** distribution — a skewed key funnels traffic to one shard (a **hot partition**) while others idle."""))

cells.append(code(r'''def shard_of(key, num_shards=4):
    return hash(key) % num_shards

# GOOD key: high-cardinality user_id spreads evenly across shards.
even_keys = [f"user-{i}" for i in range(1000)]
# BAD key: almost everything shares one value (e.g. region="US") -> one hot shard.
skewed_keys = (["US"] * 900) + [f"region-{i}" for i in range(100)]

def distribution(keys):
    counts = {s: 0 for s in range(4)}
    for k in keys:
        counts[shard_of(k)] += 1
    return counts

even = distribution(even_keys)
skew = distribution(skewed_keys)
print("EVEN key (user_id) :", even,
      f"-> max/min = {max(even.values()) / max(min(even.values()),1):.1f}x")
print("SKEWED key (region):", skew,
      f"-> one shard holds {max(skew.values())} of {sum(skew.values())} rows (HOT)")''' ))

cells.append(md(r"""**What you just saw.** The high-cardinality `user_id` spread roughly evenly across all four shards; the low-cardinality `region` dumped ~90% of traffic onto a single shard while the others idled. That hot shard becomes your bottleneck and single point of failure — and the partition key is a **one-way door** (re-sharding live data is painful). Ch 30 makes this choice its centerpiece."""))

cells.append(md(r"""## 🎯 Senior lens

The deepest lesson of this chapter is about **what *not* to build**. The outbox and saga are patterns you *do* hand-roll — they're application-level coordination. But genuine **distributed consensus** — agreeing on a leader, a lock, a committed value across nodes under partial failure — is a graveyard of subtle, data-corrupting bugs. The senior move is to **delegate** it: reach for **etcd**, **ZooKeeper**, your database's transactions, or a managed primitive, and recognize the moment you've wandered into consensus so you can step back to a proven tool.

So the dividing line: use the **outbox** to keep your own state and events consistent, use a **saga** to coordinate a multi-step process across services — and the instant you find yourself wanting a distributed lock or leader election, *stop and use a system built for it*. Knowing **when** you're in consensus territory is worth more than knowing Paxos. This is the correctness substrate the Ch 31 workers stand on, and it foreshadows the Part XI "architecting at scale" pass."""))

cells.append(md(r"""## Recap

- The **dual-write** problem: a crash between a DB commit and a broker publish leaves them permanently disagreeing — you can't make the two atomic directly.
- The **transactional outbox** writes the business row and the event-to-publish in **one** local transaction; a relay publishes them **at-least-once**.
- At-least-once means duplicates are normal, so the **consumer must be idempotent** (29-02) — outbox + idempotent sink is the correct pair.
- **Logical clocks** (version numbers) order events across nodes without trusting wall-clock time.
- A **saga** coordinates multi-service steps with **compensating actions** run in reverse on failure; compensations are real, idempotent operations.
- Partition keys must spread load **evenly**; a low-cardinality key creates a **hot partition** (Ch 30). And: **delegate consensus** to etcd/ZooKeeper/DB transactions — never hand-roll it."""))

cells.append(md(r"""## Exercises

Predict the result before running each.

1. **Add a compensation.** Extend the saga with a 4th step (`send_confirmation` / `send_cancellation`). Make step 4 fail and confirm the compensations unwind steps 3→2→1 in order. Predict the final `state`.
2. **Make the relay crash-safe.** Add a `mark_published` that can be lost (crash before it commits). Re-run the relay twice and show the idempotent consumer still yields exactly one side effect.
3. **Pick a better key.** In section 6, design a composite partition key that keeps a tenant's data together *and* spreads tenants evenly. Predict its distribution versus the skewed `region` key.
4. **Order under concurrency.** Give two nodes the *same* version number for different payloads. How does `sorted` break the tie, and what real-world rule (e.g. node id tiebreak) would you add to make the order total and deterministic?"""))

cells.append(code('# Exercise 1 — your code here\n'))
cells.append(code('# Exercise 2 — your code here\n'))
cells.append(code('# Exercise 3 — your code here\n'))
cells.append(code('# Exercise 4 — your code here\n'))

cells.append(md(r"""## Next

- ⬅️ **Previous:** [`29-02-idempotency-retries-exactly-once-myth.ipynb`](./29-02-idempotency-retries-exactly-once-myth.ipynb).
- ➡️ **Next chapter:** Ch 30 (databases at scale) makes the **partition-key** choice its centerpiece — the hot-partition demo here is the warm-up.
- 📘 **Applied in the blueprint:** the resilience instincts feed [`blueprints/agent-loop/`](../../../blueprints/agent-loop/) (idempotent, retried tool calls) and the event-driven glue in the capstone.
- 🏗️ **Capstone:** the outbox/saga and idempotency are the correctness substrate for `capstone/workers/` — Ch 31's Celery tasks (`acks_late` ⇒ at-least-once ⇒ idempotent) are exactly the *idempotent consumer* built here.
- See the book **§29.5** (partitioning & replication), **§29.7** (time/ordering, logical clocks, transactional outbox, sagas with compensations)."""))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print("wrote", os.path.abspath(OUT), "cells:", len(cells))
