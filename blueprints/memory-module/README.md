# 🧠 Memory Module — pattern blueprint

> Realizes book **Ch 14 — Memory & State** · standalone version of the capstone [`memory/`](../../capstone) module
> · pairs with [`agent-loop`](../agent-loop/PLAN.md), summarizes through [`llm-gateway`](../llm-gateway/PLAN.md)

A **layered memory module** for agents. An agent that can't remember restarts every turn; this is
the infrastructure that lets state survive **a turn, a session, and a restart** — without blowing
the context window or the budget.

It is a *reference implementation to study and adapt*, not an answer key to clone (see the
[blueprint catalog](../README.md)). It runs **free and offline in `MOCK=1`** (the default): the
summarizer is a deterministic mock and relevance is lexical, so there is **no API spend and no
required keys**. The core imports only the Python **standard library**.

---

## The layers

```text
        agent reads/writes ─────────────►  MemoryStore  (store.py)  ◄──── the only surface you need
                                              │
                 ┌────────────────────────────┼───────────────────────────────┐
                 ▼                             ▼                               ▼
        WorkingMemory (working.py)   LongTermMemory (longterm.py)     PersistenceBackend (backends/)
        the live window:             durable facts/episodes,          survive a restart:
        token budget +               read by relevance                in-memory (MOCK) │ sqlite (file)
        summarize-on-overflow        (recency tiebreak)               └─ Postgres = prod swap
                 │
                 ▼
        Summarizer (summarize.py) — rolling summary of evicted turns
        MockSummarizer (offline)  │  gateway-backed (live, llm-gateway)
```

| Layer | File | Responsibility |
|---|---|---|
| **Working memory** | `working.py` | The live conversation window under a token budget. Overflows are **summarized, not dropped**. |
| **Long-term memory** | `longterm.py` | Durable facts/episodes, retrieved by **relevance** (recency as a tiebreak). |
| **Summarizer** | `summarize.py` | Folds evicted turns into a rolling summary. `MockSummarizer` offline; gateway-backed live. |
| **Persistence** | `backends/` | Makes both layers durable. `InMemoryBackend` (MOCK) and `SQLiteBackend` (file); Postgres is the prod swap. |
| **Facade** | `store.py` | `MemoryStore` — the four verbs an agent uses: `remember`, `memorize`, `recall`, `context`. |

---

## Quickstart

```bash
# From this directory. No install, no keys, no spend.
python demo.py
```

The demo runs two sessions against a throwaway SQLite file: session 1 learns a fact and chats
until the window overflows and **summarizes**; the store is saved and closed; session 2 opens a
**fresh store on the same file** (a simulated restart) and **recalls the fact** learned before.

```python
from memory_module import MemoryStore, SQLiteBackend

store = MemoryStore.open("user-42", SQLiteBackend("memory.sqlite"), token_budget=512)
store.set_system("You are a concise assistant.")
store.remember("user", "My name is Ada and I work on payments.")
store.memorize("The user's name is Ada.", kind="fact")   # promote a durable fact
store.save()                                              # persist both layers

# ...later, even after a process restart...
store = MemoryStore.open("user-42", SQLiteBackend("memory.sqlite"))
store.recall("what is the user's name?")     # → [MemoryRecord("The user's name is Ada.")]
store.context()                              # system + rolling summary + recent turns
```

Run the tests:

```bash
pip install pytest        # the only test dependency
pytest                    # 24 tests: overflow→summarize, relevance read, persistence
```

---

## The policies (this is the part worth reading)

### 1. Window budget — summarize, don't truncate

The working window is finite. The naive overflow handler drops the oldest turns; the agent then
forgets mid-conversation with **no trace**. Instead, `WorkingMemory` folds each evicted turn into a
**rolling summary** before removing it (`_compact_if_needed`), so the information survives in a
smaller footprint. `keep_last` turns are always retained verbatim so immediate context is never
summarized away.

> Token counting is a dependency-free heuristic (`estimate_tokens`, ~4 chars/token). Swap in
> `tiktoken` for exact accounting in production — the policy is unchanged.

### 2. Summarize vs. evict vs. promote to long-term

Three different moves for three different needs:

- **Summarize** (automatic): conversational continuity. Lossy and recency-biased — under sustained
  pressure the *oldest* fragment is eventually squeezed out of the bounded summary. That is by
  design; a 12-token window cannot retain everything.
- **Evict** (automatic, after summarizing): reclaim the budget.
- **Promote to long-term** (explicit, `memorize()`): anything that must outlive the conversation —
  a name, a preference, a decision — goes to durable memory. **This is why the demo recalls "Ada"
  after a restart even though the working summary may have dropped it.** Don't rely on the rolling
  summary for facts you can't lose; promote them.

The rolling summary is bounded to a **fraction of the token budget** (`summary_budget_ratio`,
default 0.5) so it can never outgrow the window it exists to shrink.

### 3. Recency vs. relevance (the long-term read)

- **Relevance** (`recall` / `search`, the default): "what do I know that bears on *this query*?"
  Scored here by lexical Jaccard overlap with a small stopword filter, so an unrelated query scores
  ~0 and returns nothing rather than noise.
- **Recency** (`recent`): "what did I learn *most recently*?" — used as the tiebreak within
  relevance, and available on its own.

> Relevance is lexical so the module stays offline. The production swap is **cosine similarity over
> embeddings** (`sentence-transformers` or a vector DB like Chroma/Pinecone — both in the repo
> `requirements.txt`). The retrieval *interface* (`search(query, top_k, kind, min_score)`) does not
> change; only the scorer does.

### 4. Persistence-backend swap

The `PersistenceBackend` Protocol (`backends/base.py`) is one small seam: `save` / `load` /
`sessions` / `close`, round-tripping one JSON-able `StoreState` per session.

| Backend | When | Durability |
|---|---|---|
| `InMemoryBackend` | MOCK default, tests | Within one process run |
| `SQLiteBackend` | local persistence, the demo | Across a real restart (single file, stdlib `sqlite3`) |
| **Postgres** (prod swap) | a real service | Across instances; the one-JSON-blob-per-session schema maps to a `jsonb` column. `psycopg` is already pinned in the repo `requirements.txt`. |

Implementing a new backend is implementing four methods. `MemoryStore` above is untouched.

---

## MOCK vs. live

| | `MOCK=1` (default) | `MOCK=0` (live) |
|---|---|---|
| Summarizer | `MockSummarizer` — deterministic, extractive, **$0** | Inject a [`llm-gateway`](../llm-gateway/PLAN.md)-backed summarizer |
| Relevance | lexical Jaccard, offline | swap in embeddings |
| Keys needed | none | provider key (via env only — see [`.env.example`](../../.env.example)) |

The `MOCK` switch comes from `COMPANION_MOCK` (per [`docs/NOTEBOOK-STANDARDS.md`](../../docs/NOTEBOOK-STANDARDS.md) §3).
**Secrets come only from the environment**, never hardcoded. `default_summarizer()` honors the
switch and **fails loudly** under `MOCK=0` rather than silently spending — you must inject a real
`Summarizer` explicitly.

### Live path (wiring the real summarizer)

The module is standalone by design — it ships the mock so the whole thing runs with zero keys. To
summarize with a real model, implement the `Summarizer` protocol over the `llm-gateway` client and
inject it; the gateway is the *single door* every model call goes through (routing, caching,
cost-metering, guards):

```python
from memory_module import MemoryStore

class GatewaySummarizer:                       # one method = the whole contract
    def __init__(self, gateway): self.gw = gateway
    def summarize(self, prior_summary, messages, *, max_chars=None):
        prompt = build_summary_prompt(prior_summary, messages, max_chars)
        return self.gw.complete(prompt).text   # routed/cached/metered/guarded by llm-gateway

store = MemoryStore(summarizer=GatewaySummarizer(my_gateway))
```

---

## Where this maps

- **Book:** Ch 14 — Memory & State (working vs. long-term, summarization/compaction, persistence,
  recency vs. relevance). Makes §14's 🔧 Build sections real.
- **`learn/` walkthrough:** [`../../learn/part-04-building-blocks-of-agents/14-memory-and-state/`](../../learn/part-04-building-blocks-of-agents/14-memory-and-state/)
  builds layered memory in isolation and **ends by pointing here**.
- **Capstone:** standalone version of the capstone [`memory/`](../../capstone) module the agents
  share for session and durable state.
- **Composes:** [`llm-gateway`](../llm-gateway/PLAN.md) (live summarizer). **Pairs with:**
  [`agent-loop`](../agent-loop/PLAN.md) — the loop reads `context()` and writes `remember()` each
  turn — but does not require it.

---

## Files

```text
memory-module/
├── README.md                  ← you are here
├── pyproject.toml             # installable package; core deps = stdlib only
├── src/memory_module/
│   ├── __init__.py            # public exports
│   ├── working.py             # short-term window: token budget, compaction trigger
│   ├── longterm.py            # durable facts/episodes, relevance retrieval
│   ├── summarize.py           # rolling summary (MockSummarizer + Summarizer protocol)
│   ├── store.py               # MemoryStore facade the agent uses
│   └── backends/
│       ├── base.py            # PersistenceBackend Protocol + StoreState
│       ├── memory.py          # in-process backend (MOCK default)
│       └── sqlite.py          # file-backed durability (Postgres = prod swap)
├── tests/
│   ├── test_working.py        # overflow → summarize, not silent truncation
│   ├── test_longterm.py       # relevance retrieval returns the right episode
│   └── test_persistence.py    # state survives a store reopen / file restart
└── demo.py                    # runnable: recalls an earlier fact after a restart, MOCK
```
