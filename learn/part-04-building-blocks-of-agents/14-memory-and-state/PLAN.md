# Ch 14 — Memory & State

> Companion plan · Part IV · book file `chapters/14-memory-and-state.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
An agent that can't remember meets you for the first time every turn. These notebooks make
the chapter's central discipline — *the context window is a scarce budget* — something the
reader feels by watching a transcript blow the budget, then taming it with the three moves
(pin / window / summarize) and a long-term store. The build assembles the book's layered
`Memory` class (the 🔧 Build) that the capstone's `memory/` module becomes; a second
walkthrough covers durable state so a run survives a crash. Crucially, it shows long-term
*semantic memory is just RAG* — so the reader reuses Ch 13's machinery instead of inventing a
new subsystem.

## Planned notebooks

### 14-01 · `14-01-context-budget-window-compaction.ipynb` — Short-term memory on a token budget
- **Type:** concept-lab
- **Maps to:** book §14.1 (context window as a budget), §14.3 (conversation memory: buffers,
  windows, token budgeting), §14.4 (summarization & compaction).
- **Objective:** manage a growing conversation under a fixed token budget by pinning
  essentials, windowing recent turns, and compacting what falls out — without losing
  decisions or open threads.
- **Prereqs:** Ch 8 (tokenizers, "lost in the middle") · Ch 11 (model APIs for the summary
  call).
- **Cell arc:**
  - 🧠 mental model: the context window as a small desk; memory = the filing cabinets/sticky
    notes deciding what's on the desk *right now*.
  - Build the book's `build_context()` sliding window (newest-first, token-budgeted) over a
    synthetic transcript.
  - ⚠️ pitfall: count *messages* instead of *tokens* — paste one giant log, watch a
    "last-10-messages" window silently blow (or waste) the budget. Budget in tokens, always.
  - 🔮 *predict*: at 70% of budget, which early turns survive pin+window vs a raw window?
  - Add the book's `compact()` step: summarize the old span into a running brief, preserve
    decisions/preferences/unfinished work, carry it forward; recurse on a long session.
  - 🎯 senior lens: salience — what *must* survive compaction (commitments, identifiers,
    open tasks) vs what's noise (pleasantries, superseded steps); trigger on a threshold,
    not every turn, to control cost.
- **Datasets/fixtures:** a generated multi-turn transcript (in-cell, seeded) + one oversized
  pasted-log message; a simple `count_tokens` (real tokenizer if available, deterministic
  fallback otherwise).
- **APIs & cost:** offline windowing; the summary/compaction call is `MOCK=1` canned
  (deterministic), live ≈ 1–2 short calls.
- **You'll be able to:** keep a long conversation inside a token budget while protecting the
  facts that matter.

### 14-02 · `14-02-long-term-memory-recall-reflection.ipynb` — 🔧 Build: layered memory (recall × write)
- **Type:** walkthrough  *(the chapter's 🔧 Build — the capstone `memory/` module)*
- **Maps to:** book §14.5 (long-term stores), §14.6 (ranking recall: relevance × recency ×
  importance; incl. §14.6.1 consolidation), §14.9 (writing: extraction/reflection, dedupe,
  forgetting), and §14.14 "Build: a layered memory module for the capstone" (the `Memory`
  class).
- **Objective:** build the book's `Memory` — a budgeted short-term buffer plus a long-term
  vector store with **ranked recall** and **reflective writes** — and see why bare top-k recall
  is not enough.
- **Prereqs:** 14-01; **Ch 13** (the vector store / retrieval stack memory reuses); Ch 12
  (tools — for the optional MemGPT-style paging aside).
- **Cell arc:**
  - 🧠 mental model + 🎯 senior lens up front: long-term *semantic memory and RAG are the same
    machinery* — embed, store, recall by similarity (so we lift Ch 13's retriever).
  - Reflective **write**: run the book's `reflect_and_store()` to extract durable facts (JSON
    list) from a conversation; **dedupe/update** instead of inserting near-copies.
  - Bare top-k recall first, then the book's `rank()` re-rank by **relevance × recency ×
    importance** (exponential recency decay, stored importance score).
  - 🔮 *predict*: a stale-but-chatty memory vs an old-but-critical "allergic to penicillin"
    fact — which wins under top-k vs the weighted blend? Run and see.
  - ⚠️ pitfall: store-everything memory *hurts* retrieval (noise crowds signal) and risks
    context poisoning / stale facts / PII — write deliberately, timestamp, forget on purpose.
  - **Consolidation**: fold ten episodic exchanges into one durable semantic fact; show the
    store shrink while recall improves.
  - Assemble the `Memory` class (`remember_turn` w/ threshold compaction, `recall`,
    `consolidate`); note the MemGPT/virtual-context alternative (model pages memory via tools)
    as a dial, default pipeline-driven.
  - 🎯 senior lens: tune the recall weights to the domain (support → recency; medical →
    importance). Close by pointing at `blueprints/memory-module/` and `capstone/memory/`.
- **Datasets/fixtures:** a small generated set of "memories" with timestamps + importance
  scores; a sample conversation to reflect over (in `data/`, tiny, committed).
- **APIs & cost:** local embeddings for the store (offline); reflection/consolidation calls
  `MOCK=1` canned, live ≈ a few short calls.
- **You'll be able to:** build a layered memory that recalls by relevance×recency×importance
  and writes only durable, deduped facts.

### 14-03 · `14-03-durable-state-checkpointing.ipynb` — State that survives a crash
- **Type:** walkthrough
- **Maps to:** book §14.10 (state & persistence for long-running agents — the `RunState`
  checkpoint pattern), with §14.11 (memory in multi-agent systems) and §14.12 (skill
  libraries) surfaced as the senior-lens/aside.
- **Objective:** checkpoint a long-running agent's state per thread id so it can crash,
  reload, and resume exactly where it left off — including pausing for human approval.
- **Prereqs:** 14-02 (so memory + state are seen as distinct concerns).
- **Cell arc:**
  - 🧠 mental model: memory = *what the model sees*; state = *surviving interruptions*
    (crashes, restarts, deploys, waiting on a human).
  - Build the book's `RunState` dataclass + a `step()` that **checkpoints after every step**
    to a tiny key→state store (a JSON/SQLite-backed `save`/`load`).
  - 🔮 *predict*: kill the process mid-run, reload by `thread_id` — does it resume or restart?
  - Model a `waiting_human` pause and resume on approval (foreshadows Ch 20 HITL).
  - ⚠️ pitfall: in-process-only state loses everything on restart; non-idempotent steps
    double-execute on resume — checkpoint outside the process, make steps replay-safe.
  - 🎯 senior lens: this checkpoint pattern *is* what LangGraph checkpointers / Temporal /
    Celery (Ch 29, 31) give you — understand the primitive before adopting the framework.
  - **Aside (concept):** multi-agent memory *scoping* (private working memory + a namespaced
    shared store = shared mutable state) and the **skill library** (`SkillLibrary`, learn only
    from *verified* successes — Ch 16) as procedural memory the capstone agents share.
- **Datasets/fixtures:** none external — a generated multi-step task; state persisted to a
  local file the cell writes (git-ignored / temp).
- **APIs & cost:** offline by default; the "agent next action" is a mock/stub so the focus
  stays on persistence (no spend); live path optional.
- **You'll be able to:** persist and resume a long agent run, and reason about memory scope
  and verified skills across agents.

## Feeds (cross-pillar)
- **Blueprint(s):** [`blueprints/memory-module/`](../../../blueprints/memory-module/) — the
  production layered memory (short-term compaction + long-term ranked recall + reflective
  writes + consolidation + skill library) behind a clean interface. 14-02 ends pointing here.
- **Template(s):** — (no template; contributes the checkpoint/`RunState` pattern reused by the
  agent-project starter and the workers/Celery setup).
- **Capstone:** advances `capstone/memory/` (the `Memory` class + ranked recall + skill
  library) and contributes the checkpoint scheme used by `capstone/agents/` and
  `capstone/workers/` (Ch 31); checkpoint `checkpoints/ch14-memory`.

## Dependencies
- **Ch 13 (RAG)** — long-term semantic memory reuses the vector store/retriever directly · Ch 8
  (tokenizers / "lost in the middle") · Ch 11 (model APIs for summary/reflection) · Ch 12
  (tools — MemGPT-style paging). Forward links: Ch 16 (verified success gates skills), Ch 20
  (HITL pause/resume), Ch 29/31 (durable execution underneath checkpointing).

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` with no errors and no key (local
  embeddings; canned summary/reflection/judge; mock agent action).
- [ ] `build_context`, `compact`, `rank`, `reflect_and_store`, the `Memory` class, and
  `RunState` match the book's §14 code and the relevance×recency×importance blend.
- [ ] 14-02 links `blueprints/memory-module/` + `capstone/memory/`; the skill library is gated
  on *verified* success exactly as the book insists.
- [ ] Each notebook ends with recap + 2–4 exercises; secrets from env only; fixtures tiny and
  committed; no PII persisted in committed outputs.
