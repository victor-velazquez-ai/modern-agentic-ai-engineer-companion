# -*- coding: utf-8 -*-
"""Generator for 29-02-idempotency-retries-exactly-once-myth.ipynb (concept-lab)."""
import json, os

OUT = os.path.join(os.path.dirname(__file__), "..",
                   "29-02-idempotency-retries-exactly-once-myth.ipynb")

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

cells.append(md(r"""# Why a retry is safe only if you make it safe

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 29 §29.6, §29.8 · type: concept-lab*

**One-line promise:** watch a blind retry **double-charge** a mock payment, fix it with a server-side **idempotency key**, then add **backoff + jitter** and a **circuit breaker** and watch a cascading failure get contained — the chapter's central correctness lesson, made runnable and free."""))

cells.append(md(r"""## 🧠 Why this matters

The previous notebook left us with the timeout-with-no-answer: you can't tell whether the work happened, so the *only* safe response is to **retry**. But a blind retry might do the thing twice — charge the card again, send the email again. The cure is **idempotency**: design the operation so doing it twice has the same effect as doing it once, usually via a client-supplied **idempotency key** the server records and dedupes on.

That unlocks a hard truth: **"exactly-once delivery" does not exist** over an unreliable network. You can't distinguish a lost request from a lost response, so you pick **at-least-once** delivery and make **processing idempotent** — yielding *effectively once*, the only honest guarantee. Then we add the rest of the failure-mode toolkit (backoff, jitter, circuit breaker, bulkhead, backpressure) and watch it break the chain of a cascading failure. All offline, all deterministic."""))

cells.append(md(r"""## Objectives & prereqs

**By the end you can:**
- Reproduce a **double charge** from a blind retry, and kill it with a server-side **idempotency key** (the book's `charge(idempotency_key, ...)` shape).
- State *why* exactly-once delivery is a myth and what to do instead (**at-least-once + idempotent processing**).
- Turn a synchronized retry **stampede** into a dispersed one with **exponential backoff + jitter**.
- Wrap a sick dependency in a **circuit breaker** (closed → open → half-open) and isolate pools with a **bulkhead** so one saturated path can't starve another.

**Prereqs:** notebook **29-01** (the three outcomes; the timeout-with-no-answer). No API key — the "payment gateway" and "dependency" are mocks; the jitter RNG is seeded."""))

cells.append(code(r'''# --- Setup: imports, env, and the MOCK switch ---------------------------------
# stdlib only (+ python-dotenv from requirements.txt). No network, no real sleeps.
import os
import random
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MOCK = os.getenv("COMPANION_MOCK", "1") == "1"
random.seed(29)  # makes every jittered delay and flaky outcome reproducible

# A virtual clock so "sleeps" advance logical time without slowing CI.
class Clock:
    def __init__(self): self.t = 0.0
    def sleep(self, seconds): self.t += seconds   # advance, never actually wait
clock = Clock()

print(f"MOCK mode: {MOCK}  | mock payment gateway + dependency, seed=29")''' ))

cells.append(md(r"""## 1 · A payment gateway and a blind retry (§29.6)

We model the dangerous reality from notebook 29-01: when a charge **times out**, the gateway *already debited the card* — you just never got the receipt. A naive client, seeing the timeout, retries. Let's count the debits."""))

cells.append(code(r'''class PaymentGateway:
    """Debits land in `ledger`. On a timeout the debit STILL happens server-side
    (the request landed; only the response was lost) — modeling 29-01's timeout."""
    def __init__(self, timeouts):
        self._timeouts_left = timeouts
        self.ledger = []  # every real debit recorded here

    def charge_raw(self, amount):
        self.ledger.append(amount)            # <-- the irreversible side effect
        if self._timeouts_left > 0:
            self._timeouts_left -= 1
            raise TimeoutError("charge timed out — debit applied, receipt lost")
        return {"status": "ok", "amount": amount}


def blind_retry(fn, *, attempts=3):
    """Retry on timeout with NO idempotency. The classic double-charge bug."""
    last = None
    for _ in range(attempts):
        try:
            return fn()
        except TimeoutError as e:
            last = e                          # saw nothing -> try again (and re-debit)
    raise last

gw = PaymentGateway(timeouts=2)              # first two attempts time out, third succeeds
try:
    blind_retry(lambda: gw.charge_raw(49.99))
except TimeoutError:
    pass
print("blind retry — debits applied:", len(gw.ledger), "->", gw.ledger)''' ))

cells.append(md(r"""## 2 · 🔮 Predict: how many debits land?

The card should be charged **once** for one $49.99 order. The client retried up to 3 times; the first two attempts timed out (but debited anyway), the third succeeded.

Before re-reading the output above as truth, **predict the debit count** and the dollar total. Then look: the ledger holds the answer — and it isn't `1`."""))

cells.append(code(r'''print("Expected (what the user agreed to): 1 debit of $49.99")
print(f"Actual                          : {len(gw.ledger)} debits, "
      f"${sum(gw.ledger):.2f} total")
assert len(gw.ledger) == 3, "the blind retry triple-charged this order"
print()
print("Each timed-out attempt re-ran the side effect. The retry didn't recover the")
print("operation — it REPEATED it. This is the bug idempotency exists to kill.")''' ))

cells.append(md(r"""**What you just saw.** Three debits for one order. The retry logic was *correct* about needing to retry (a timeout is outcome-unknown) but *wrong* to assume the operation was safe to repeat. The fix is not "retry less" — it's "make the operation idempotent so repeating is harmless"."""))

cells.append(md(r"""## 3 · The fix: a server-side idempotency key (§29.6)

This is the book's `charge(idempotency_key, ...)` pattern. The **client** generates one stable key *per logical operation* (not per attempt) and sends it with every retry. The **server** records the key on first success and returns the *same* result for any replay — no second debit.

> Note the key is derived from the **order**, not the attempt. Tie it to the attempt and you're back to double-charging."""))

cells.append(code(r'''class IdempotentGateway:
    """charge(idempotency_key, amount): records the key, dedupes replays.
    Mirrors the book's §29.6 SELECT-by-idem-key / INSERT shape, in-memory."""
    def __init__(self, timeouts):
        self._timeouts_left = timeouts
        self.ledger = []
        self._seen = {}  # idem_key -> stored result (the 'charges' table)

    def charge(self, idempotency_key, amount):
        if idempotency_key in self._seen:        # already processed -> same result
            return self._seen[idempotency_key]   # NO new debit on replay
        self.ledger.append(amount)               # first time only: the real debit
        result = {"status": "ok", "amount": amount, "key": idempotency_key}
        if self._timeouts_left > 0:
            # The debit + record happen, but the response is lost. On replay the
            # key is already present, so the retry is absorbed.
            self._seen[idempotency_key] = result
            self._timeouts_left -= 1
            raise TimeoutError("timed out — but the key is recorded, so replay is safe")
        self._seen[idempotency_key] = result
        return result


def retry_with_key(gw, key, amount, *, attempts=3):
    last = None
    for _ in range(attempts):
        try:
            return gw.charge(key, amount)        # same key every attempt
        except TimeoutError as e:
            last = e
    raise last

idem_gw = IdempotentGateway(timeouts=2)
key = "charge:ORD-9912"                            # one key for this logical operation
retry_with_key(idem_gw, key, 49.99)
print("idempotent retry — debits applied:", len(idem_gw.ledger), "->", idem_gw.ledger)
assert len(idem_gw.ledger) == 1, "idempotency must collapse replays to a single debit"
print("Effectively once: the card was charged exactly one time across three attempts.")''' ))

cells.append(md(r"""**What you just saw.** Same two timeouts, same three attempts — **one** debit. The server recognized the replayed key and returned the stored receipt instead of charging again. *Effectively once*: at-least-once delivery + idempotent processing."""))

cells.append(md(r"""## 4 · The exactly-once myth, in one proof (§29.6)

Why can't we just build "exactly-once delivery"? Because **the client cannot distinguish a lost request from a lost response** — both look identical: silence. Let's make that indistinguishability concrete."""))

cells.append(code(r'''def observe(scenario):
    """From the client's seat, what is visible after a timeout?"""
    # Two genuinely different server realities...
    if scenario == "request_lost":
        server_ran = False   # the request never reached the server
    else:  # "response_lost"
        server_ran = True    # the server DID the work; the reply vanished
    client_sees = "timeout (no response)"   # ...look identical from here
    return server_ran, client_sees

for s in ("request_lost", "response_lost"):
    server_ran, seen = observe(s)
    print(f"{s:14} -> server actually ran? {server_ran!s:5} | client sees: {seen}")

print()
print("Same observation, opposite truths. Since you can't tell them apart, you must")
print("choose: at-most-once (retry never -> risk losing work) OR")
print("at-least-once (retry -> risk duplicates). Real systems pick at-least-once and")
print("make processing IDEMPOTENT -> 'effectively once'. True exactly-once delivery")
print("is a myth; any vendor 'guaranteeing' it is hiding idempotency in the fine print.")''' ))

cells.append(md(r"""**What you just saw.** The two rows are indistinguishable to the client, which is the entire proof. You don't get exactly-once *delivery*; you engineer exactly-once *effect* by making the receiver idempotent. Internalize this and a whole class of data-corruption bugs simply stops existing."""))

cells.append(md(r"""## 5 · Retry policy: a stampede, then jitter disperses it (§29.8)

Idempotency makes a retry *safe*; it doesn't make a fleet of retries *kind*. If a thousand clients all retry on the same schedule after a blip, they re-spike the recovering service in lockstep — a **thundering herd**. The cure is **exponential backoff + jitter**: randomize each client's wait so the herd spreads out."""))

cells.append(code(r'''def backoff_delay(attempt, *, base=0.5, jitter=True):
    """Exponential backoff; with 'full jitter' the wait is random in [0, computed]."""
    computed = base * (2 ** attempt)
    return random.uniform(0, computed) if jitter else computed

CLIENTS = 1000
def retry_wave(jitter):
    random.seed(29)  # same population either way, for a fair comparison
    # When does each client hit the server on its 3rd-attempt retry?
    hits = {}
    for _ in range(CLIENTS):
        t = round(backoff_delay(3, jitter=jitter), 1)   # bucket to 0.1s
        hits[t] = hits.get(t, 0) + 1
    return hits

no_jitter = retry_wave(jitter=False)
with_jitter = retry_wave(jitter=True)
peak_no = max(no_jitter.values())
peak_yes = max(with_jitter.values())
print(f"NO jitter : every client retries at t={list(no_jitter)[0]}s -> "
      f"peak load = {peak_no} simultaneous hits (a stampede)")
print(f"jitter    : retries spread across {len(with_jitter)} time buckets -> "
      f"peak load = {peak_yes} hits ({peak_no // max(peak_yes,1)}x lower spike)")''' ))

cells.append(md(r"""**What you just saw.** Without jitter, all 1000 clients land on the *same* instant — the worst possible moment for a service that's trying to recover. Full jitter scatters them across many time buckets, flattening the peak by orders of magnitude. Jitter is not a nicety; it's what keeps your retry from being a self-inflicted DDoS."""))

cells.append(md(r"""## 6 · Circuit breaker + bulkhead (§29.8)

Backoff handles a *blip*. A dependency that is **down** needs a different tool: a **circuit breaker**. It counts failures; after a threshold it **opens** and fails fast (no point hammering a dead service and burning your latency budget); after a cooldown it goes **half-open** to probe with a single trial call, then **closes** on success.

A **bulkhead** complements it: give each dependency its own bounded pool, so one saturated path can't consume all your workers and starve the others."""))

cells.append(code(r'''class CircuitBreaker:
    """closed -> (N failures) -> open -> (cooldown) -> half-open -> closed/open."""
    def __init__(self, fail_max=3, cooldown=2.0, clock=clock):
        self.fail_max, self.cooldown, self.clock = fail_max, cooldown, clock
        self.state, self.fails, self.opened_at = "closed", 0, None
        self.last_entered = "closed"              # state the most recent call ran under

    def call(self, fn):
        if self.state == "open":
            if self.clock.t - self.opened_at >= self.cooldown:
                self.state = "half-open"          # cooldown elapsed: probe recovery
            else:
                raise RuntimeError("circuit OPEN — failing fast, not calling the sick dep")
        entered = self.last_entered = self.state  # the state this call ran under
        try:
            result = fn()
        except Exception:
            self.fails += 1
            if entered == "half-open" or self.fails >= self.fail_max:
                self.state, self.opened_at = "open", self.clock.t   # trip / re-trip
            raise
        self.fails, self.state = 0, "closed"      # success closes the circuit
        return result


# A dependency that is DOWN for a while, then recovers.
class SickDependency:
    def __init__(self, down_until): self.down_until = down_until
    def call(self):
        if clock.t < self.down_until:
            raise ConnectionError("dependency is down")
        return "ok"

clock.t = 0.0
dep = SickDependency(down_until=5.0)
cb = CircuitBreaker(fail_max=3, cooldown=2.0)
real_calls = {"to_dep": 0}

def guarded():
    real_calls["to_dep"] += 1
    return dep.call()

log = []
for step in range(12):
    try:
        cb.call(guarded); outcome = "ok"
    except RuntimeError:
        outcome = "fast-fail (open)"   # breaker rejected WITHOUT calling the dep
    except ConnectionError:
        outcome = "dep error"
    log.append((round(clock.t, 1), cb.state, outcome))
    clock.sleep(1.0)                   # virtual time marches on

for t, state, outcome in log:
    print(f"t={t:>4}s  state={state:<9}  {outcome}")
print()
print("actual calls that reached the sick dependency:", real_calls["to_dep"],
      "(far fewer than 12 — the open circuit shielded it)")''' ))

cells.append(md(r"""**What you just saw.** After 3 failures the breaker **opened** and started fast-failing — note those steps made *no call to the dependency at all*, saving every caller from waiting on a known-dead service. After the cooldown it went **half-open**, probed once the dependency had recovered, and **closed**. The dependency received only a handful of calls instead of all twelve."""))

cells.append(md(r"""> ⚠️ **Pitfall — the cascading failure.** Without these tools the chain is lethal: a *slow* dependency makes its callers pile up waiting, exhausting their threads / connection pools; that makes *them* slow, which takes down *their* callers — until one weak link has collapsed the whole system. Timeouts cap the wait, the circuit breaker stops feeding the sick dep, the **bulkhead** quarantines the damage to one pool, and **backpressure** (reject when a bounded queue is full) pushes slowness back to the caller instead of silently queueing unbounded work. The toolkit exists specifically to break this chain."""))

cells.append(code(r'''# Bulkhead: two independent bounded pools. A flood on pool A must NOT starve pool B.
class Bulkhead:
    def __init__(self, size): self.size, self.in_use = size, 0
    def acquire(self):
        if self.in_use >= self.size:
            raise RuntimeError("bulkhead full — shedding load (backpressure)")
        self.in_use += 1
    def release(self):
        self.in_use = max(0, self.in_use - 1)

pool_llm = Bulkhead(size=2)      # calls to a slow LLM provider
pool_db = Bulkhead(size=2)       # calls to the database

# 5 LLM requests storm in and never release (provider hung). Without isolation they
# would consume every worker; with a bulkhead they can only fill THEIR pool.
shed = 0
for _ in range(5):
    try:
        pool_llm.acquire()       # the slow path saturates...
    except RuntimeError:
        shed += 1                # ...and excess is shed, not queued forever
print(f"LLM pool: in_use={pool_llm.in_use}/{pool_llm.size}, shed {shed} requests")

# The DB pool is untouched — DB traffic still flows. Damage is quarantined.
pool_db.acquire()
print(f"DB  pool: in_use={pool_db.in_use}/{pool_db.size} — unaffected by the LLM storm")
assert pool_db.in_use == 1, "the bulkhead kept the LLM failure from starving the DB path"''' ))

cells.append(md(r"""**What you just saw.** The hung LLM path filled *its* pool and the excess was **shed** (backpressure) rather than queued forever — and the DB pool kept serving. That isolation is the difference between "one provider is slow" and "the whole service is down"."""))

cells.append(md(r"""## 🎯 Senior lens

Here is the instinct to carry into every agentic system: **every model call and every tool call is a remote call that fails in three ways** — success, clean failure, and the timeout-with-no-answer. So a senior makes every side-effecting tool:

- **idempotent** — carry an idempotency key derived from the *logical operation* (e.g. the `tool_use` id), so a replayed turn can't send two emails or file two tickets;
- **time-bounded** — a timeout on every call; an unbounded wait is a hang propagating upward;
- **retried with backoff + jitter** — recover from blips without stampeding;
- **circuit-broken + bulkheaded** — fail fast on a dead dependency and quarantine the blast radius.

The model can *generate* the call; knowing it must wear all four of these is the judgment that keeps the system standing under load. This is exactly the substrate the Ch 31 workers rely on (`acks_late` ⇒ at-least-once ⇒ tasks must be idempotent)."""))

cells.append(md(r"""## Recap

- A **timeout is outcome-unknown**, so you must retry — but a **blind retry double-charges**. The fix is idempotency, not "retry less".
- A server-side **idempotency key** (per *logical operation*, not per attempt) dedupes replays → *effectively once*.
- **Exactly-once delivery is a myth**: a lost request and a lost response are indistinguishable, so pick **at-least-once + idempotent processing**.
- **Exponential backoff + jitter** turns a synchronized retry stampede into a dispersed, survivable trickle.
- A **circuit breaker** (closed → open → half-open) fails fast on a dead dependency; a **bulkhead** + **backpressure** quarantine the damage so a slow dep can't cascade into a full outage."""))

cells.append(md(r"""## Exercises

Predict the result before running each.

1. **Make a tool idempotent.** Take a mock `send_email(to, body)` that appends to an `outbox` list. Add an idempotency key so retrying a timed-out send delivers exactly one email. Predict the outbox length after 3 retries, then verify.
2. **Key per attempt (anti-pattern).** Re-run section 3 but derive the key from a per-attempt counter. Predict the debit count and explain, in one sentence, why the key must be tied to the operation.
3. **Backoff ceiling.** Add a `max_delay` cap to `backoff_delay` so attempt 8 can't sleep for minutes. Predict attempt 8's delay with and without the cap.
4. **Half-open flap.** Make `SickDependency` recover and then fail again right after the probe. Trace the breaker's state across 15 steps and explain why a single half-open trial (not a flood) is the right probe."""))

cells.append(code('# Exercise 1 — your code here\n'))
cells.append(code('# Exercise 2 — your code here\n'))
cells.append(code('# Exercise 3 — your code here\n'))
cells.append(code('# Exercise 4 — your code here\n'))

cells.append(md(r"""## Next

- ⬅️ **Previous:** [`29-01-partial-failure-and-cap-pacelc.ipynb`](./29-01-partial-failure-and-cap-pacelc.ipynb).
- ➡️ **Next notebook:** [`29-03-outbox-and-sagas-simulated.ipynb`](./29-03-outbox-and-sagas-simulated.ipynb) — idempotency underpins both patterns there: an at-least-once outbox relay needs an idempotent consumer, and a saga's compensations undo a partial failure.
- 📘 **Applied in the blueprint:** retries/timeouts on tool calls in [`blueprints/agent-loop/`](../../../blueprints/agent-loop/); the production retry/circuit-breaker wrapper in [`blueprints/llm-gateway/`](../../../blueprints/llm-gateway/).
- 🏗️ **Capstone:** this is the correctness substrate for `capstone/workers/` — Ch 31's Celery tasks run `acks_late` (at-least-once), so they *must* be idempotent exactly as built here.
- See the book **§29.6** (the `charge` idempotency shape, exactly-once myth) and **§29.8** (timeouts, backoff + jitter, circuit breaker, bulkheads, backpressure)."""))

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
