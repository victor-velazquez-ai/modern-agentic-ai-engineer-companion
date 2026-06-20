# Blueprint — Memory Module  (pattern)

> Realizes book Ch 14 · mirrors capstone `memory/` · Status: 📋 planned (Phase 1)

## What it is
A **layered memory module** for agents: short-term **working memory** (the live conversation
window, with summarization/compaction when it overflows) and long-term memory (durable facts and
episodes, retrieved by relevance) behind a **persistence** adapter. A clean `MemoryStore` surface
an agent reads from and writes to, so state survives a turn, a session, and a restart.

## Why a blueprint (not a notebook)
- The Ch 14 notebook teaches the *idea* of layered memory; the working module — eviction policy,
  summarization trigger, recency-vs-relevance read, persistence — is real infrastructure.
- `agent-loop` and the supervisor read/write through it, and solution blueprints persist state
  with it, so it needs a stable, importable interface.
- "When to summarize vs. evict vs. promote to long-term" is a tested policy, not a snippet.

## Planned structure
```text
memory-module/
├── README.md                  # the layers, eviction/summarization policy, persistence, adapt
├── pyproject.toml
├── src/memory_module/
│   ├── __init__.py
│   ├── working.py             #   short-term window: token budget, compaction trigger
│   ├── longterm.py            #   durable facts/episodes, relevance retrieval
│   ├── summarize.py           #   rolling summary when the window overflows (mock summarizer)
│   ├── store.py               #   MemoryStore facade the agent uses
│   └── backends/
│       ├── base.py            #   Persistence Protocol
│       ├── memory.py          #   in-process backend (MOCK default)
│       └── sqlite.py          #   file-backed durability (Postgres noted as the prod swap)
├── tests/
│   ├── test_working.py        #   overflow → summarize, not silent truncation
│   ├── test_longterm.py       #   relevance retrieval returns the right episode
│   └── test_persistence.py    #   state survives a store reopen
└── demo.py                    # runnable: a chat that recalls an earlier fact after restart, MOCK
```

## Composes / depends on
- **`llm-gateway`** — for the summarization/compaction call (mock summarizer keeps it standalone).
- Pairs with **`agent-loop`** (the loop reads/writes memory each turn) but does not require it.

## Maps to the book
- **Ch 14 — Memory & State:** working vs. long-term memory, summarization/compaction, persistence,
  recency vs. relevance. Makes §14's 🔧 Build sections real.
- **`learn/` walkthrough:** [`../../learn/part-04-building-blocks-of-agents/14-memory-and-state/`](../../learn/part-04-building-blocks-of-agents/14-memory-and-state/)
  builds layered memory in isolation and **ends by pointing here**.

## Maps to the capstone
Standalone version of capstone **`memory/`** — the layered memory module (Ch 14) the capstone's
agents share for session and durable state.

## Phase-2 definition of done
- [ ] `pytest tests/` passes; overflow→summarize, relevance read, and persistence covered.
- [ ] `python demo.py` recalls an earlier fact across a simulated restart in **`MOCK=1`** (no spend).
- [ ] README explains trade-offs: window budget, summarize-vs-evict, promotion to long-term,
      recency-vs-relevance, and the persistence-backend swap.
- [ ] Cross-links (`llm-gateway`, `agent-loop`, the Ch 14 walkthrough, capstone `memory/`) resolve.
