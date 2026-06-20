"""Generator for 14-03-durable-state-checkpointing.ipynb."""
import os

from _nbgen import Q3, code, md, write_nb

HERE = os.path.dirname(os.path.abspath(__file__))
cells = []

cells.append(md(r"""
# State that survives a crash

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 14 §14.10–§14.12 · type: walkthrough*

**The promise:** checkpoint a long-running agent's state per `thread_id` so it can crash, reload, and resume *exactly* where it left off — including pausing for human approval. You'll build the book's `RunState` + a checkpoint-after-every-step loop, then kill the process mid-run and watch it resume.
"""))

cells.append(md(r"""
## 🧠 Why this matters: memory vs state

Two different concerns, often confused:

- **Memory** is *what the model sees* — the conversation, recalled facts, the scratchpad (notebooks 14-01 and 14-02).
- **State** is *what survives interruptions* — crashes, restarts, deploys, or an agent that pauses for hours awaiting a human.

A long-running agent needs durable, **resumable** state: the goal, the plan, completed steps, and pending work, written somewhere *outside* process memory. The pattern is **checkpointing** — after each meaningful step, persist the run's state under a stable thread id, so the agent can be reloaded and continue exactly where it left off.
"""))

cells.append(md(r"""
## Objectives & prereqs

**By the end you can:**
- model a run with the book's `RunState` dataclass;
- checkpoint after *every* step to a tiny key→state store (JSON-backed);
- crash and resume a run by `thread_id` instead of restarting it;
- pause on `waiting_human` and resume on approval; reason about idempotent (replay-safe) steps.

**Prereqs:** [`14-02`](./14-02-long-term-memory-recall-reflection.ipynb) (so memory and state are seen as distinct concerns).

**Run first:** nothing — offline by default; the "agent next action" is a deterministic stub so the focus stays on persistence (no spend). State is written to a local temp file the cell creates.
"""))

cells.append(code(rf"""
# --- Setup ---------------------------------------------------------------
# Fully offline: the agent's 'next action' is a stub, so this notebook is about
# PERSISTENCE, not model calls. No API key, no spend, in any mode.
import json
import os
import random
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MOCK = os.getenv("COMPANION_MOCK", "1") == "1"  # live path optional; default offline
random.seed(14)

# Checkpoints go to a temp dir so nothing is committed; treat it as git-ignored.
CKPT_DIR = Path(tempfile.gettempdir()) / "ch14_checkpoints"
CKPT_DIR.mkdir(exist_ok=True)
print(f"MOCK        = {{MOCK}}")
print(f"checkpoints = {{CKPT_DIR}}  (temp / git-ignored)")
"""))

cells.append(md(r"""
## The `RunState` and a checkpoint store

`RunState` (§14.10) is the whole run as plain data: a `thread_id`, the `goal`, the `steps_done`, the `pending` work, and a `status` lifecycle (`running | waiting_human | done | failed`). Because it's plain data, it serializes to JSON and reloads anywhere — a process, a different machine, a worker (Ch 31).

The store is a trivial `save`/`load` keyed by `thread_id`. We use JSON files; swap in SQLite or Redis without touching the loop.
"""))

cells.append(code(rf"""
@dataclass
class RunState:
    thread_id: str
    goal: str
    steps_done: list = field(default_factory=list)
    pending: list = field(default_factory=list)
    status: str = "running"          # running | waiting_human | done | failed


class CheckpointStore:
    {Q3}A tiny key->state store. JSON files here; SQLite/Redis in production.{Q3}

    def __init__(self, root: Path):
        self.root = root

    def _path(self, thread_id):
        return self.root / f"{{thread_id}}.json"

    def save(self, thread_id, state: RunState):
        self._path(thread_id).write_text(json.dumps(asdict(state), indent=2),
                                         encoding="utf-8")

    def load(self, thread_id):
        p = self._path(thread_id)
        if not p.exists():
            return None
        return RunState(**json.loads(p.read_text(encoding="utf-8")))


store = CheckpointStore(CKPT_DIR)
print("RunState + CheckpointStore ready.")
"""))

cells.append(md(r"""
## A step loop that checkpoints after every step

The agent's `next_action` is a deterministic stub here (offline). The load-bearing line is the one that **checkpoints after every step** — that single `store.save(...)` is what turns a fragile in-process run into a resumable one.
"""))

cells.append(code(rf"""
def next_action(state: RunState):
    {Q3}Deterministic stub for the agent's next action (no model call).

    Pops the next pending item. The 'deploy' step asks for human approval, to
    show the waiting_human pause. In MOCK=0 you'd swap in a real agent here.
    {Q3}
    task = state.pending[0]
    needs_approval = task.startswith("deploy")
    return {{"task": task, "result": f"did: {{task}}", "needs_approval": needs_approval}}


def step(state: RunState, store: CheckpointStore):
    result = next_action(state)
    state.steps_done.append(result)
    state.pending.pop(0)
    if result.get("needs_approval"):
        state.status = "waiting_human"
    elif not state.pending:
        state.status = "done"
    store.save(state.thread_id, state)        # <-- checkpoint after EVERY step
    return state


# Start a run with four steps; 'deploy' will pause for approval.
THREAD = "order-4711"
state = RunState(thread_id=THREAD, goal="Reconcile + deploy invoice 4711",
                 pending=["fetch order", "match line items", "deploy fix", "notify user"])
store.save(THREAD, state)

# Run until we either finish or hit a human gate.
while state.status == "running":
    state = step(state, store)
print(f"status after first run: {{state.status}}")
print(f"steps done: {{[s['task'] for s in state.steps_done]}}")
print(f"pending   : {{state.pending}}")
"""))

cells.append(md(r"""
🔮 **Predict — then run the next cell.** We now *simulate a crash*: throw away the in-memory `state` object entirely (as if the process died), then `load` the run back by `thread_id` from the checkpoint store. Does it **resume** from where it paused (deploy pending approval) or **restart** from scratch?
"""))

cells.append(code(rf"""
# Simulate a crash: the process dies, all in-memory state is gone.
del state                       # poof — no more in-process object

# A fresh process / worker reloads by thread_id alone.
reloaded = store.load(THREAD)
print(f"reloaded thread '{{reloaded.thread_id}}'")
print(f"  status      : {{reloaded.status}}")
print(f"  steps_done  : {{[s['task'] for s in reloaded.steps_done]}}")
print(f"  pending     : {{reloaded.pending}}")
print("\nIt RESUMED: the two completed steps are intact and 'deploy' is still pending. "
      "Nothing re-ran.")
"""))

cells.append(md(r"""
## Pause for a human, resume on approval

The run is parked at `waiting_human` — it will sit there safely across restarts until a human acts. On approval we flip the status back to `running` and continue the loop. (This foreshadows the human-in-the-loop pattern in Ch 20.)
"""))

cells.append(code(rf"""
def approve(thread_id, store):
    {Q3}Human approves the gated step; the run becomes resumable again.{Q3}
    s = store.load(thread_id)
    assert s.status == "waiting_human", f"nothing waiting on {{thread_id}}"
    s.status = "running"
    store.save(thread_id, s)
    return s


state = approve(THREAD, store)            # a human clicks 'approve'
while state.status == "running":
    state = step(state, store)
print(f"final status: {{state.status}}")
print(f"all steps   : {{[s['task'] for s in state.steps_done]}}")
"""))

cells.append(md(r"""
## ⚠️ Pitfall: in-process state and non-idempotent steps

Two ways this bites in production:

1. **In-process-only state** loses everything on restart. If `RunState` lives only in a variable (or a request-scoped object), a deploy or a crash wipes the run. Checkpoint *outside* the process — file, DB, or a durable queue.
2. **Non-idempotent steps double-execute on resume.** If a step *charged a card* and then the process died *before* the checkpoint wrote, a naive resume runs it again. Make steps **replay-safe**: an idempotency key, an "already done?" check, or write-the-result-then-checkpoint in one transaction.

Let's show the double-execution hazard concretely.
"""))

cells.append(code(rf"""
# A non-idempotent side effect: charging a card. Naive resume can double-charge.
charges = []


def charge_card(order_id):
    charges.append(order_id)               # the side effect
    return f"charged {{order_id}}"


# Replay-safe wrapper: skip if this thread already charged (idempotency key).
def charge_once(thread_id, order_id, already_done: set):
    key = f"{{thread_id}}:charge:{{order_id}}"
    if key in already_done:
        return f"skipped (already charged {{order_id}})"
    result = charge_card(order_id)
    already_done.add(key)
    return result


done_keys = set()
# First attempt charges; a 'crash + resume' replays the SAME step.
print(charge_once(THREAD, "4711", done_keys))   # charges
print(charge_once(THREAD, "4711", done_keys))   # resume -> skipped, no double charge
print(f"total charges recorded: {{len(charges)}} (idempotency kept it at 1)")
"""))

cells.append(md(r"""
## 🎯 Senior lens: you just built a checkpointer

This checkpoint-after-every-step pattern **is** what the heavy machinery gives you:

- **LangGraph checkpointers** persist graph state per thread so agents pause and resume — the same `save(thread_id, state)` you just wrote.
- **Temporal** and **Celery** (Ch 29, 31) provide durable execution and scheduling for long or asynchronous runs.

Understand the primitive *before* adopting the framework: every one of them is doing this underneath. Reach for them once your agents outlive a single request — but the design questions (what's in the state, when to checkpoint, are steps replay-safe) are yours regardless of the tool, and they don't go away when you adopt a framework.
"""))

cells.append(md(r"""
## Aside (concept): memory scope across agents, and verified skills

Two §14.11–§14.12 ideas the capstone agents share — concept here, built in the blueprint:

**Multi-agent memory scoping.** Give each agent **private working memory** (its scratchpad) and a single **namespaced shared store** (the common goal, established facts, a task board). That shared store is **shared mutable state** in a concurrent system — with every consistency hazard that implies. Get the boundaries wrong and you get either agents that repeat each other's work, or a blackboard too noisy to use.

**The skill library = procedural memory.** Memory so far remembered *facts* and *what happened*; the most valuable thing an agent remembers is *how to do things*. After an agent **verifiably** succeeds, distil the approach into a named, reusable `procedure`, index it by the task it solves, and retrieve it before the next similar task. The single load-bearing word is **verified** — store an approach from an *unverified* run and you teach the agent its own mistakes, and a bad procedure retrieved confidently every run is far more corrosive than a bad fact.
"""))

cells.append(code(rf"""
# The book's SkillLibrary (§14.12): learn ONLY from verified successes.
class SkillLibrary:
    def __init__(self, vectors, embed):
        self.vectors, self.embed = vectors, embed

    def save_skill(self, task, procedure, verified):
        {Q3}Only learn from VERIFIED successes (Ch 16). Never learn a bad habit.{Q3}
        if not verified:
            return                              # <-- the load-bearing guard
        self.vectors.append({{"task": task, "procedure": procedure,
                             "kind": "procedural"}})

    def retrieve_skills(self, task, k=3):
        {Q3}Pull relevant procedures to seed planning a new task.{Q3}
        # Stub similarity: substring overlap on the task string (offline).
        ranked = sorted(self.vectors,
                        key=lambda s: len(set(task.split()) & set(s["task"].split())),
                        reverse=True)
        return [s["procedure"] for s in ranked[:k]]


skills = SkillLibrary(vectors=[], embed=lambda t: t)
# A run that PASSED its verifier (Ch 16) -> the skill is saved.
skills.save_skill("reconcile invoice", "fetch order; match by SKU; flag >$1", verified=True)
# A run the agent *believed* succeeded but did NOT verify -> dropped on the floor.
skills.save_skill("reconcile invoice", "guess and hope", verified=False)

print("stored skills:", len(skills.vectors), "(only the verified one)")
print("retrieved    :", skills.retrieve_skills("reconcile invoice for order 4711"))
"""))

cells.append(md(r"""
## Recap

- **Memory ≠ state.** Memory = what the model sees; state = what survives interruptions.
- `RunState` is plain data (goal, steps_done, pending, status) → serializes and reloads anywhere.
- **Checkpoint after every step** under a stable `thread_id`; a crash then *resumes* instead of restarting.
- Park at `waiting_human` and resume on approval (Ch 20 HITL).
- ⚠️ Checkpoint *outside* the process, and make steps **idempotent** so resume can't double-execute side effects.
- This primitive is exactly what LangGraph checkpointers / Temporal / Celery provide — learn it before adopting the framework.
- Across agents: **scope** memory (private + namespaced shared), and learn skills **only from verified successes**.
"""))

cells.append(md(r"""
## Exercises

(Solutions live in `solutions/`, not inline.)

1. **Crash mid-step.** Make `next_action` raise *after* appending to `steps_done` but *before* `store.save`. Predict what `load` returns after the crash, and fix the loop so the step is replay-safe.
2. **SQLite store.** Reimplement `CheckpointStore` over `sqlite3` (same `save`/`load` interface). Predict what changes in the step loop. (Answer: nothing — that's the point.)
3. **Two threads.** Run `order-4711` and `order-4712` interleaved through the same store. Confirm their checkpoints never collide, and explain how `thread_id` scopes the state.
4. **Verified-only skills.** Extend `save_skill` to also record a `success_rate`; add a `retire(min_rate)` that drops skills whose rate decayed (skill rot, §14.12). Show a rotted skill stops being retrieved.
"""))

cells.append(code(r"""
# Exercise 1 — crash between append and checkpoint; make the step replay-safe.
"""))

cells.append(code(r"""
# Exercise 2 — reimplement CheckpointStore over sqlite3 (same interface).
"""))

cells.append(code(r"""
# Exercise 3 — run two threads through one store without collision.
"""))

cells.append(code(r"""
# Exercise 4 — add success_rate + retire(min_rate) to fight skill rot.
"""))

cells.append(md(r"""
## Next

- **Blueprint:** [`../../../blueprints/memory-module/`](../../../blueprints/memory-module/) — the production memory layer plus the verified **skill library** the capstone agents share.
- **Forward:** Ch 20 (human-in-the-loop pause/resume) · Ch 29 & 31 (Temporal / Celery durable execution underneath this checkpoint pattern).
- **Capstone:** this checkpoint scheme is reused by `capstone/agents/` and `capstone/workers/` (Ch 31); checkpoint `checkpoints/ch14-memory`.
"""))

out = write_nb(os.path.join(HERE, "14-03-durable-state-checkpointing.ipynb"), cells)
print("wrote", out)
