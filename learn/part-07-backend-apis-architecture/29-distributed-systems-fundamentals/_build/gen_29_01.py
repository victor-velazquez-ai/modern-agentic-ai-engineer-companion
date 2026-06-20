# -*- coding: utf-8 -*-
"""Generator for 29-01-partial-failure-and-cap-pacelc.ipynb (concept-lab)."""
import json, os

OUT = os.path.join(os.path.dirname(__file__), "..",
                   "29-01-partial-failure-and-cap-pacelc.ipynb")

def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(text)}

def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": _lines(text)}

def _lines(text):
    # nbformat stores source as a list of lines, each (except last) ending in \n.
    text = text.rstrip("\n")
    parts = text.split("\n")
    return [p + "\n" for p in parts[:-1]] + [parts[-1]]

cells = []

cells.append(md(r"""# The timeout with no answer, simulated

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 29 §29.1–29.3 · type: concept-lab*

**One-line promise:** feel the three outcomes of every remote call — success, clean failure, and the dreaded *timeout with no answer* — then force the CAP choice during a simulated partition and pay the PACELC latency tax when there *isn't* one. All in-process, no cluster, no spend."""))

cells.append(md(r"""## 🧠 Why this matters

The instant your code talks to a second machine, two comfortable truths from single-process programming evaporate. **Partial failure:** a call can succeed, fail cleanly, or *hang and time out with no answer at all* — and that third outcome is the heart of distributed systems, because you genuinely cannot tell whether the side effect happened. **No global clock:** there is no single "now" two nodes agree on, so "which write came first?" stops being obvious.

Reading those sentences is easy; *believing* them in your bones is what changes how you design. So instead of trusting a real flaky network, we build a tiny one in memory — an injectable clock and a `flaky_call` you can dial — and watch the laws bite. Everything here runs free, offline, and deterministically."""))

cells.append(md(r"""## Objectives & prereqs

**By the end you can:**
- Name the **three** outcomes of any remote call and explain why the timeout is categorically the scary one.
- Tick which of the **eight fallacies** a given bug violated.
- Run a two-node store through a **partition** and choose **CP** (refuse / stale-error) vs **AP** (serve stale, reconcile later) — observing what each returns mid-partition.
- Measure the **PACELC** *else*-branch tax: stronger consistency costs a coordination round-trip even when nothing is broken.

**Prereqs:** Ch 4 (async), Ch 24 (request lifecycle, first idempotency intro). No API key, no network — the simulation is fully offline."""))

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

# This notebook is a SIMULATION: there is no live path to hit. MOCK stays 1 so the
# whole repo shares one switch; here it simply documents "offline by construction."
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"
random.seed(29)  # every flaky outcome and partition below reproduces exactly

print(f"MOCK mode: {MOCK}  | distributed system simulated in-process, seed=29")''' ))

cells.append(md(r"""## 1 · The three outcomes of a remote call (§29.1)

On one machine a function call either returns or raises — two outcomes. Across a network there is a **third**: the request leaves, and *no answer comes back*. The server may have done the work, or not. You cannot know from where you stand.

We model this with a `Network` whose *injectable clock* never really sleeps (so CI is instant) and a `flaky_call(p_fail, p_timeout)` that returns, raises, or **hangs → times out**."""))

cells.append(code(r'''class Timeout(Exception):
    """No response arrived in time. OUTCOME UNKNOWN — the work may or may not have run."""

class Network:
    """An injectable, virtual network. `clock` advances logically; nothing really sleeps."""
    def __init__(self):
        self.clock = 0.0          # virtual seconds — advanced, never slept on
        self.partitioned = False  # toggled in section 3

    def advance(self, seconds):
        self.clock += seconds     # the only "time" that passes in this notebook


net = Network()

def flaky_call(net, *, p_fail=0.2, p_timeout=0.2, work=None):
    """A remote call with three possible outcomes.

    Returns the work's result, raises ConnectionError (clean failure), or raises
    Timeout (no answer). Crucially, on a timeout the side effect in `work` STILL RUNS
    on the server first — modeling 'the request landed but the reply was lost.'"""
    roll = random.random()
    net.advance(0.05)  # the round-trip "costs" virtual latency
    if roll < p_timeout:
        if work is not None:
            work()                       # the server did the work...
        raise Timeout("read timeout — no response")  # ...but you never heard back
    if roll < p_timeout + p_fail:
        raise ConnectionError("connection reset before the request was handled")
    if work is not None:
        work()
    return "OK"

print("network + flaky_call ready")''' ))

cells.append(md(r"""## 2 · 🔮 Predict: after a timeout, did the side effect happen?

We'll fire the call many times against a server-side counter that increments **once per landed request**. Some calls succeed, some fail cleanly, some time out.

Before running: **for the calls that timed out, did the counter advance?** Can the *client* tell a timed-out-but-completed call apart from a timed-out-and-dropped one?"""))

cells.append(code(r'''server_side_effects = {"count": 0}
def do_work():
    server_side_effects["count"] += 1

outcomes = {"OK": 0, "clean_failure": 0, "timeout": 0}
random.seed(29)  # reproduce the exact sequence
for _ in range(40):
    try:
        flaky_call(net, p_fail=0.25, p_timeout=0.25, work=do_work)
        outcomes["OK"] += 1
    except Timeout:
        outcomes["timeout"] += 1          # client saw NOTHING — but work may have run
    except ConnectionError:
        outcomes["clean_failure"] += 1    # safe: the request never executed

print("client-visible outcomes:", outcomes)
print("server side effects that ACTUALLY landed:", server_side_effects["count"])
print()
print("Successes the client knows about :", outcomes["OK"])
print("Effects the server really applied:", server_side_effects["count"],
      "(> successes — every timeout that completed is an effect the client can't see)")''' ))

cells.append(md(r"""**What you just saw.** The server applied *more* effects than the client counted as successes. Every one of those extras is a **timeout that completed on the server** — work that happened while the client saw only silence. A clean `ConnectionError` is safe (the request never ran); the `Timeout` is the one that haunts you, because *"did it happen?"* has no answer from the client's side. That single fact is why the next notebook is entirely about idempotency."""))

cells.append(md(r"""## 3 · The eight fallacies, as a checklist (§29.2)

In 1994 Sun's engineers catalogued the false assumptions that sink distributed systems. Each is a single-machine habit that is *wrong* across a network. Tick the one a bug violated and the root cause usually names itself."""))

cells.append(code(r'''FALLACIES = [
    "The network is reliable",
    "Latency is zero",
    "Bandwidth is infinite",
    "The network is secure",
    "Topology doesn't change",
    "There is one administrator",
    "Transport cost is zero",
    "The network is homogeneous",
]

# A worked example: classify which fallacies each incident "assumed away".
incidents = {
    "Blind retry of a timed-out charge double-billed a card":
        ["The network is reliable"],
    "Agent fanned 1 request into 30 model calls; p99 latency exploded":
        ["Latency is zero", "Bandwidth is infinite"],
    "Token leaked because an internal hop was assumed trusted":
        ["The network is secure"],
    "Hardcoded a replica's IP; it moved during autoscaling and 404'd":
        ["Topology doesn't change"],
}

for incident, violated in incidents.items():
    ticks = [f"[x] {f}" if f in violated else f"[ ] {f}" for f in FALLACIES]
    print(incident)
    for t in ticks:
        if t.startswith("[x]"):
            print("   ", t)
    print()''' ))

cells.append(md(r"""**What you just saw.** Naming the fallacy turns a vague "flaky" incident into a precise design fix: *the network is reliable* → add idempotent retries; *latency is zero* → batch and cache the fan-out. For AI engineers this compounds — agentic systems are unusually **chatty**, so every fallacy gets multiplied by the number of model and tool hops behind one user request."""))

cells.append(md(r"""## 4 · CAP: the choice you make *during* a partition (§29.3)

When data lives on two nodes and the link between them drops (a **partition**), physics forces a choice: stay **consistent** (refuse to serve possibly-stale data, erroring instead) or stay **available** (answer anyway, possibly stale, and reconcile later). You cannot have both *during the partition*.

We build a two-node store. Node A takes the write; with the partition up, A can't replicate to B. Watch what a read from **B** returns under each policy."""))

cells.append(code(r'''@dataclass
class TwoNodeStore:
    """Primary 'a' replicates to 'b'. A partition blocks replication."""
    net: Network
    mode: str = "CP"                       # "CP" or "AP"
    a: dict = field(default_factory=dict)  # primary
    b: dict = field(default_factory=dict)  # replica

    def write(self, key, value):
        self.a[key] = value                # the primary always accepts the write
        if not self.net.partitioned:
            self.b[key] = value            # replicate only if the link is up
        return "written to primary"

    def read_from_replica(self, key):
        """A read served by node B while A may be ahead of it."""
        if self.net.partitioned:
            if self.mode == "CP":
                # Consistency: refuse rather than risk returning stale data.
                raise ConnectionError("CP: replica refuses — may be stale during partition")
            else:
                # Availability: answer with whatever B has, even if behind.
                return self.b.get(key, None)  # possibly stale / missing
        return self.b.get(key)             # healthy: B is up to date


for mode in ("CP", "AP"):
    net.partitioned = False
    store = TwoNodeStore(net=net, mode=mode)
    store.write("balance", 100)            # replicated fine, link healthy
    net.partitioned = True                 # <-- the link drops
    store.write("balance", 250)            # primary advances; replica is now behind
    print(f"[{mode}] mid-partition read from replica:", end=" ")
    try:
        print(store.read_from_replica("balance"))
    except ConnectionError as e:
        print(f"ERROR -> {e}")''' ))

cells.append(md(r"""**What you just saw.** Same partition, two philosophies. **CP** refuses the replica read (an error beats a wrong answer — think bank balance). **AP** happily returns the **stale `100`** and reconciles once the link heals (a stale read beats an outage — think a "likes" counter). Neither is "correct" in the abstract; the feature decides."""))

cells.append(md(r"""> ⚠️ **Pitfall — "CAP means pick two of three."** That framing is wrong and it leads people to believe they can *design away* partitions. You can't: on a real network, partitions **will** happen, so you don't get to drop **P**. The only real choice is what to do *during* one — **CP** (sacrifice availability) or **AP** (sacrifice consistency). State it as "what happens during a partition?", never "which two letters do I keep?"."""))

cells.append(md(r"""## 5 · PACELC: the *else* tax you pay every day (§29.3)

CAP only speaks about the partition. **PACELC** finishes the sentence: *if Partition then choose A or C, **Else** (no partition) you still trade **L**atency against **C**onsistency.* Stronger consistency needs **coordination** — extra round-trips to agree — and coordination costs latency on *every healthy request*, not just during failures.

We compare a fast **eventual** read (answer from the nearest replica) against a **strong** read that does a "quorum" round-trip to confirm it has the latest value. The injectable clock makes the cost visible without any real waiting."""))

cells.append(code(r'''ONE_HOP = 0.05  # virtual seconds for a single node round-trip

def eventual_read(net):
    """Read the local replica immediately. Cheap, maybe slightly stale."""
    start = net.clock
    net.advance(ONE_HOP)                 # one local hop
    return net.clock - start

def strong_read(net, replicas=3):
    """Confirm the value with a quorum before answering. Correct, but coordinated."""
    start = net.clock
    net.advance(ONE_HOP)                 # ask the local node...
    quorum = replicas // 2 + 1           # majority needed
    net.advance(ONE_HOP * (quorum - 1))  # ...plus round-trips to reach a majority
    return net.clock - start

ev = eventual_read(net)
st = strong_read(net, replicas=3)
print(f"eventual (no coordination): {ev*1000:.0f} ms  (1 hop)")
print(f"strong   (quorum of 2/3) : {st*1000:.0f} ms  ({st/ev:.0f}x slower) <- the 'Else' tax")
print()
print("No partition occurred. Strong consistency still cost extra latency, every call.")''' ))

cells.append(md(r"""**What you just saw.** With the network perfectly healthy, the strongly-consistent read was several times slower — purely because it had to *coordinate*. That is the PACELC *else* branch: consistency is not free even in the sunny case. A senior chooses the weakest consistency the feature can tolerate precisely to stop paying this tax on every healthy request."""))

cells.append(md(r"""## 🎯 Senior lens

The amateur question is *"is the system consistent?"* — a yes/no that has no good answer. The senior question is *"**which** consistency does **this feature** actually need?"*, asked per read path:

- A chat session reading back the message it just sent → **read-your-writes** (a user must see their own action).
- A user's account balance → **strong** (a stale balance is a bug with a dollar sign).
- An aggregate usage dashboard or a "trending" count → **eventual** is fine; nobody is harmed by a few seconds of lag, and you save the coordination tax.

Consistency is a **dial you set per feature**, not a global switch — and every notch toward "strong" is paid for in latency (PACELC) and availability (CAP). Spend it where correctness demands, save it everywhere else."""))

cells.append(md(r"""## Recap

- Every remote call has **three** outcomes: success, clean failure, and the **timeout with no answer** — the client cannot tell a completed-but-unacknowledged call from a dropped one.
- The **eight fallacies** are single-machine habits that are false across a network; naming the violated one usually names the fix. Agentic systems are *chatty*, so the fallacies compound per hop.
- **CAP** is not "pick two of three": partitions are inevitable, so the choice is **CP** (refuse / error) vs **AP** (serve stale, reconcile) *during* a partition.
- **PACELC** adds the *else* branch: even with no partition, stronger consistency costs a **coordination round-trip** — latency you pay on every healthy request.
- Consistency is **per-feature**: read-your-writes for a chat session, strong for a balance, eventual for a dashboard."""))

cells.append(md(r"""## Exercises

Predict the result before running each.

1. **Tune the danger.** Re-run section 2 with `p_timeout=0.5`. Predict the gap between client-visible successes and real server effects, then confirm. What does a higher timeout rate do to your need for idempotency (next notebook)?
2. **Read-your-writes on AP.** Extend `TwoNodeStore` so a client that *just wrote* to A is routed back to A for its next read (sticky routing), even in AP mode. Show that this gives read-your-writes without going fully strong.
3. **PACELC sweep.** Make `strong_read` take `replicas=5`. Predict the new quorum size and the latency multiple versus `eventual_read`, then verify. Why does the cost grow with replica count?
4. **Classify a real outage.** Pick a bug you've hit (a duplicate email, a stale cache, a hang). Tick which of the eight fallacies it assumed away, and name the one design change that would have prevented it."""))

cells.append(code('# Exercise 1 — your code here\n'))
cells.append(code('# Exercise 2 — your code here\n'))
cells.append(code('# Exercise 3 — your code here\n'))
cells.append(code('# Exercise 4 — your code here\n'))

cells.append(md(r"""## Next

- ➡️ **Next notebook:** [`29-02-idempotency-retries-exactly-once-myth.ipynb`](./29-02-idempotency-retries-exactly-once-myth.ipynb) — take the timeout-with-no-answer you just felt and make retries *safe*: idempotency keys, backoff + jitter, and a circuit breaker.
- 📘 **Applied in the blueprint:** these resilience instincts show up as retries/timeouts on tool calls in [`blueprints/agent-loop/`](../../../blueprints/agent-loop/).
- 🏗️ **Capstone:** this is the correctness substrate for `capstone/workers/` (idempotent, at-least-once tasks in Ch 31) and the Part XI "architecting at scale" pass.
- See the book **§29.1–29.3** for the fallacies table, CAP/PACELC, and the consistency spectrum."""))

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
