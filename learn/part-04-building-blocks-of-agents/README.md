# Part IV — Building Blocks of Agents (Ch 12–15)

> 📓 Companion to **Modern Agentic AI Engineer** · Part IV · `learn/part-04-building-blocks-of-agents/`
> Status: 📋 planned (Phase 1) — these folders hold `PLAN.md` files; notebooks land in Phase 2.

## What this part adds to the book

This is where an LLM stops being a text generator and becomes an *agent*. Part IV is the
**core hands-on heart** of the companion: four chapters, each a guided **walkthrough** that
builds one real mechanism end to end — the tool-use loop, retrieval, memory, and reliable
structured output. Unlike the practice-heavy Part II, every chapter here **feeds a blueprint
and a capstone module**, so the notebooks are the toy you build to understand, and each one
*ends by pointing at the production version* you'll study and lift:

- You don't read about the tool-use loop — you build a framework-free `while`-loop agent and
  watch the model and your code take turns (Ch 12).
- You don't read that retrieval is the weak link — you chunk a messy doc, retrieve, rerank,
  and then *measure* recall on a golden set and see exactly where quality leaks (Ch 13).
- You don't read that "an agent needs memory" — you blow a token budget, tame it with
  pin/window/compact, and rank recall by relevance × recency × importance (Ch 14).
- You don't read "validate model output" — you build the one `complete_structured` choke
  point with constrained decoding, bounded retries, repair, and a designed failure path (Ch 15).

These four chapters assemble the **agent's spine** that the capstone is built from, and they
build on each other: Ch 12's tool loop is the host, Ch 13's retriever becomes Ch 14's
long-term semantic memory (*same machinery*), and Ch 15's contracts make every model call in
the chapters that follow parseable and observable. Everything runs **offline and free** by
default — local embeddings/rerankers and a `MOCK=1` covenant stand in for the network and the
model; live API paths are documented and opt-in.

## Chapters in this part

| Ch | Title | Companion emphasis | Notebooks | Plan |
|---|---|---|---|---|
| 12 | Tool Use & Function Calling | Walkthrough — build the tool-use loop from scratch (no framework), then parallel calls + error recovery → `agent-loop` blueprint, capstone `agents/raw` | 3 | [PLAN](12-tool-use-and-function-calling/PLAN.md) |
| 13 | Retrieval-Augmented Generation (RAG) | Walkthroughs — chunk→embed→retrieve→rerank, 🔧 grounded cited answers, + a RAG-eval scorecard on a golden set → `rag-pipeline` blueprint, capstone `rag/` | 3 | [PLAN](13-retrieval-augmented-generation/PLAN.md) |
| 14 | Memory & State | Walkthroughs — token-budgeted short-term memory, 🔧 layered long-term memory (ranked recall + reflective writes), durable checkpointed state → `memory-module` blueprint, capstone `memory/` | 3 | [PLAN](14-memory-and-state/PLAN.md) |
| 15 | Structured Outputs, Validation & Reliability | Walkthroughs — schema-first + constrained decoding, then 🔧 the validate→retry→repair→degrade choke point → capstone `llm/structured` | 2 | [PLAN](15-structured-outputs-and-reliability/PLAN.md) |

## Feeds at a glance

- **Blueprints:** Ch 12 → [`blueprints/agent-loop/`](../../blueprints/agent-loop/) ·
  Ch 13 → [`blueprints/rag-pipeline/`](../../blueprints/rag-pipeline/) ·
  Ch 14 → [`blueprints/memory-module/`](../../blueprints/memory-module/). (Ch 15 ships no
  standalone blueprint — its patterns are consumed by the agent-loop and eval blueprints.)
- **Capstone:** Ch 12 → `agents/raw` + `agents/tools` · Ch 13 → `rag/` (+ golden set into
  `evals/`) · Ch 14 → `memory/` (+ the checkpoint scheme used by `agents/` and `workers/`) ·
  Ch 15 → `llm/structured.py`, the platform-wide structured-output choke point.
- **Templates:** none owned here — these chapters contribute patterns (tool definitions, the
  grounding/citation prompt, the `complete_structured` shape) that the `agent-project-starter`
  and FastAPI service templates reuse.

## Suggested path

Run the chapters **in order** — they compound. Ch 12 builds the tool loop everything else
plugs into; Ch 13 builds retrieval that Ch 14 then *reuses* as long-term memory; Ch 14 adds
the memory and durable state a real agent needs; Ch 15 makes every model interaction reliable
and observable, the contract the rest of the book depends on. New to the repo? Start with Part
I's [`03-mental-model`](../part-01-landscape-and-mindset/03-mental-model/PLAN.md) for the map
and make sure Part III (the LLM substrate, Ch 8–11) is read first — these walkthroughs assume
model APIs, embeddings, and prompting.

See [`docs/REPO-PLAN.md`](../../docs/REPO-PLAN.md) for the full chapter→asset map and
[`docs/CONVENTIONS.md`](../../docs/CONVENTIONS.md) for the `PLAN.md` template these follow.
