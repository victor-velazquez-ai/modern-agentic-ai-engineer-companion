# Ch 18 — The Framework Landscape

> Companion plan · Part V · book file `chapters/18-framework-landscape.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
You've built every internal a framework hides (Ch 12–17), so this chapter is where you learn to
*evaluate* frameworks rather than be impressed by them. The headline asset is the chapter's
🔧 **Build** (§18.7): the **same** capstone research agent implemented three ways — raw Anthropic
SDK, LangGraph, Pydantic AI — run side by side so the trade-offs (explicitness, durable state,
typed boundaries) stop being abstract. A companion concept-lab turns the chapter's decision
matrix into a reusable scorer so "name the forces first, open the matrix second" becomes a
habit. The notebooks reinforce the chapter's transparency test: never adopt what you couldn't
re-implement crudely in a week.

## Planned notebooks

### 18-01 · `18-01-same-agent-three-ways.ipynb` — 🔧 One agent, three frameworks, one diff
- **Type:** walkthrough  *(this is the chapter's 🔧 Build, §18.7)*
- **Maps to:** §18.7 (🔧 Build: one capstone agent, three ways), drawing on §18.2 (LangGraph:
  graph/state machine, checkpointers, interrupts) and §18.3 (Pydantic AI: type-safety first).
- **Objective:** implement the *same* research agent (`search_docs` → cited answer) in raw SDK,
  LangGraph, and Pydantic AI, then read the three side by side to see exactly what each
  framework gives and hides.
- **Prereqs:** Ch 12 (raw tool loop) · Ch 13 (`search_docs` retriever, mockable) · Ch 14
  (checkpoints — what LangGraph's checkpointer automates) · Ch 15 (structured outputs — what
  Pydantic AI validates at the boundary).
- **Cell arc:**
  - 🧠 mental model: a framework is a *loan of architecture* — working structure now, repaid in
    flexibility later; the five things every framework sells (loop, state, integrations,
    orchestration, production rim).
  - Define the shared contract once: the `search_docs` tool + the task ("answer from the docs,
    cite source ids, say so if uncovered").
  - *Raw SDK* (§18.7): the explicit `while` loop you own end-to-end — nothing hides from a debugger.
  - *LangGraph* (§18.7): `create_react_agent` + `InMemorySaver` — the loop collapses to a
    declaration; persistence is a constructor argument (Ch 14 checkpoints, built in).
  - *Pydantic AI* (§18.7): `Agent(output_type=CitedAnswer)` + `@agent.tool_plain` — the answer
    arrives *validated* (`answer`, `source_ids`, `confidence`), auto-retried on schema failure.
  - 🔮 *predict* which version is longest and which hides the most before reading them together;
    then compare line counts and "what's hidden from a debugger" per version.
  - ⚠️ pitfall: "gentle on the demo, brutal at the edges" — show where the magic would force
    you to reverse-engineer prompt assembly (the 2 a.m. token-bill scenario).
  - 🎯 senior lens: the capstone's division of labor — Pydantic AI for typed single-agent
    components, LangGraph where durable multi-step orchestration earns its ceremony, raw SDK
    kept alive in tests as the reference so the team never loses the wire.
- **Datasets/fixtures:** a tiny doc set in `data/` shared by all three implementations; one mock
  `rag_search` so every version returns identical, deterministic results.
- **APIs & cost:** mockable (one canned tool-use + final answer reused across all three; the
  point is *shape*, not output); live ≈ one short run per framework (3 short runs).
- **You'll be able to:** read any of the three styles fluently and articulate, in code, what you
  delegate and what it costs to leave.

### 18-02 · `18-02-choosing-a-framework.ipynb` — From forces to a defensible choice
- **Type:** concept-lab
- **Maps to:** §18.1 (what frameworks give; abstraction cost; the transparency test), §18.4–§18.6
  (LlamaIndex; CrewAI/AutoGen/Smolagents/DSPy; vendor agent SDKs incl. the Claude Agent SDK),
  §18.8 (choosing — or not choosing — as an architect; the decision matrix).
- **Objective:** turn instinct into explicit trade-off analysis — name a system's forces, then
  read the matrix — and record the decision as an ADR with its exit cost.
- **Prereqs:** 18-01; Ch 27 (ADRs / trade-off analysis); Ch 28 (hexagonal — keeping domain out
  of the framework).
- **Cell arc:**
  - Map the landscape: a small table the reader fills in — LangChain/LangGraph, Pydantic
    AI/Instructor, LlamaIndex, CrewAI/AutoGen, Smolagents/DSPy, vendor SDKs — what each is *for*.
  - The transparency test as a function: score a candidate on "could I re-implement this crudely
    in a week?" and "can I read its assembled prompts and wire calls?"
  - 🔮 *predict* the sound default for three scenarios (typed API service; long stateful
    workflow with HIL gates; RAG over private corpora), then check against §18.8's matrix.
  - ⚠️ pitfall: choosing by demo/landing page — weigh frameworks by their *worst day* (issue
    tracker, one request traced through source, 2 a.m. debugging).
  - The lock-in hedge: handoff/tool *schemas* (Ch 15/17) and MCP (Ch 19) travel across every
    framework and vendor SDK here — so the portable artifacts are the ones to invest in.
  - Generate a tiny ADR stub for a chosen scenario: forces, decision, rejected options, exit cost.
  - 🎯 senior lens: keep your *domain* (schemas, prompts, tools, evals) in framework-free
    modules the orchestration layer merely calls — that one hexagonal habit converts "rewrite"
    into "re-wire" when you switch; re-evaluate yearly, migrate rarely.
- **Datasets/fixtures:** none (a worksheet-style scorer + ADR stub generated in-cell).
- **APIs & cost:** none/offline by design (this is judgment and structure, not model calls).
- **You'll be able to:** name a system's forces before naming a framework, apply the
  transparency test, and write the ADR that makes the choice defensible.

## Feeds (cross-pillar)
- **Blueprint(s):** the three-ways comparison documents the shape used across
  [`blueprints/agent-loop/`](../../../blueprints/agent-loop/) and
  [`blueprints/multi-agent-supervisor/`](../../../blueprints/multi-agent-supervisor/) (raw vs
  framework realizations of the same contract).
- **Template(s):** the ADR stub feeds [`templates/adr-template/`](../../../templates/adr-template/);
  framework-choice defaults inform [`templates/agent-project-starter/`](../../../templates/agent-project-starter/).
- **Capstone:** builds `capstone/agents/graph/` (LangGraph) and `capstone/agents/pydantic_ai/`
  alongside the raw `capstone/agents/raw/` kept as the reference; checkpoint
  `checkpoints/ch18-three-ways`.

## Dependencies
- Ch 12 (raw loop) · Ch 13 (`search_docs`) · Ch 14 (checkpoints) · Ch 15 (structured outputs) ·
  Ch 17 (the team this chapter rebuilds) · Ch 27/28 (ADRs, hexagonal). Feeds Ch 19 (every
  framework here speaks MCP) · Ch 20 (LangGraph interrupts == the approval-gate pattern).

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` with no errors; the three implementations
      produce the *same* mocked cited answer so the diff is purely structural.
- [ ] Raw/LangGraph/Pydantic-AI code matches the book's §18.7 sketches (API shapes flagged as
      "verify against current docs"); `CitedAnswer` matches §18.7.
- [ ] 18-02 produces a real ADR stub (forces, decision, rejected options, exit cost) and applies
      the transparency test as code.
- [ ] Recap + 2–4 exercises per notebook; secrets from env only; links resolve to the
      blueprints, `templates/adr-template/`, and the capstone `agents/` subdirs.
