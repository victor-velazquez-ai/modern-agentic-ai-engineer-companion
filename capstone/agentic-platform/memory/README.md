# `memory/` — layered memory + checkpoint persistence

> Capstone subsystem (Appendix C · `memory/`) · realizes book **Ch 14 — Memory & State** · the
> assembled counterpart to the [`memory-module`](../../../blueprints/memory-module/) blueprint.

The infrastructure that lets an agent keep state across **a turn, a session, and a restart** —
and lets a worker **checkpoint a long-running run and resume it** — without blowing the context
window or the budget. It runs **free and offline by default** (`COMPANION_MOCK=1`): a
deterministic summarizer, lexical relevance, and an in-process backend, so a fresh `MemoryStore`
needs no keys, no files, and no spend. The core imports only the standard library.

```text
        agent reads/writes ─────────────►  MemoryStore  (store.py)  ◄──── the four-verb surface
                                              │
                 ┌────────────────────────────┼───────────────────────────────┐
                 ▼                             ▼                               ▼
        WorkingMemory (working.py)   LongTermMemory (longterm.py)     PersistenceBackend (backends/)
        live window: token budget    durable facts/episodes,          survive a restart:
        + summarize-on-overflow      read by relevance                in-memory (MOCK) │ sqlite (file)
                 │                   (recency tiebreak)                └─ Postgres = prod swap
                 ▼                                                              ▲
        Summarizer (summarize.py)                                              │
        MockSummarizer (offline) │ gateway-backed (live)        CheckpointStore (checkpoint.py)
                                                                snapshot a run by run_id → resume
```

## The four verbs (this is all an agent needs)

```python
from memory import MemoryStore, SQLiteBackend

store = MemoryStore.open("user-42", SQLiteBackend("memory.sqlite"), token_budget=512)
store.set_system("You are a concise assistant.")
store.remember("user", "My name is Ada and I work on payments.")  # → working window
store.memorize("The user's name is Ada.", kind="fact")            # → durable long-term
store.save()                                                      # persist both layers

# ...later, even after a process restart...
store = MemoryStore.open("user-42", SQLiteBackend("memory.sqlite"))
store.recall("what is the user's name?")  # → [MemoryRecord("The user's name is Ada.")]
store.context()                           # system + rolling summary + recent turns
```

## Checkpoints — resume a long-running run

A worker executing an agent run checkpoints after each step; a crash, redeploy, or
pause-for-approval doesn't lose the run. The checkpoint captures the memory state **plus** a small
JSON-able `agent_state` blob the loop owns (step index, pending tool calls, scratchpad):

```python
from memory import MemoryStore, CheckpointStore, SQLiteBackend

cps = CheckpointStore(SQLiteBackend("runs.sqlite"))
cps.checkpoint("run-123", store, step=4, agent_state={"pending_tool": "search_docs"},
               status="awaiting_approval")

# ...new worker, after a crash / approval...
store, cp = cps.resume("run-123")   # memory restored; cp.step == 4, cp.agent_state recovered
```

## The policies worth reading

| Policy | Where | Rule |
|---|---|---|
| **Summarize, don't truncate** | `working.py` | On overflow, fold the oldest turn into a *rolling summary* before evicting it; `keep_last` recent turns are never summarized away. |
| **Bounded summary** | `working.py` | The rolling summary is capped at `summary_budget_ratio` of the token budget, so it can never outgrow the window it shrinks. |
| **Summarize vs. promote** | `store.py` | The rolling summary is lossy/recency-biased; anything that must outlive the chat is **promoted** to long-term via `memorize()`. |
| **Relevance vs. recency** | `longterm.py` | `recall`/`search` read by **relevance** (lexical Jaccard, stopword-filtered) with recency as the tiebreak; an unrelated query returns nothing, not noise. |
| **Last-write-wins checkpoint** | `checkpoint.py` | One current checkpoint per `run_id`; resume needs only the latest. |

## Layout

| Path | What it does |
|---|---|
| `working.py` | short-term window: token budget, summarize-on-overflow compaction |
| `longterm.py` | durable facts/episodes, relevance retrieval (recency tiebreak) |
| `summarize.py` | rolling summary (`MockSummarizer` + `Summarizer` protocol; live = `llm/` gateway) |
| `store.py` | `MemoryStore` facade: `remember` / `memorize` / `recall` / `context` + save/load |
| `checkpoint.py` | `Checkpoint` + `CheckpointStore`: snapshot a run by id, resume after crash/approval |
| `backends/base.py` | `PersistenceBackend` protocol + `StoreState` — the persistence seam |
| `backends/memory.py` | in-process backend (MOCK default) |
| `backends/sqlite.py` | file-backed durability; Postgres is the prod swap at the same interface |

## MOCK vs. live & secrets

- **MOCK by default** (`COMPANION_MOCK=1`): `MockSummarizer` (deterministic, `$0`), lexical
  relevance, in-process backend. Identical results every run.
- **Live** (`COMPANION_MOCK=0`): inject a `llm/`-gateway-backed `Summarizer`; `default_summarizer()`
  **fails loudly** rather than silently spending if none is wired in. Embedding-based relevance is
  the production swap for `longterm.search` (same interface).
- **Secrets from env only**: the live summarizer reads provider keys via the gateway; nothing here
  is hardcoded.

## Maps to the book

- **Ch 14 — Memory & State:** working vs. long-term, summarization/compaction, persistence,
  recency vs. relevance, run checkpoints.
- **Blueprint:** [`memory-module`](../../../blueprints/memory-module/) is the same layering in
  isolation; this is the integrated capstone subsystem the agents and workers share.
