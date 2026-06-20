# Ch 17 — Multi-Agent Systems

> Companion plan · Part V · book file `chapters/17-multi-agent-systems.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
The chapter's thesis is that a multi-agent system *is* a distributed system and most teams
reach for one too soon. The notebooks make that concrete: first a concept-lab that lets the
reader *feel* the counter-forces — compounding error across handoffs, the cost of a lost
message — and choose a topology deliberately; then the chapter's 🔧 **Build** (§17.5), a working
supervisor-plus-specialists team where each specialist is exposed to the supervisor as a tool.
That build is the capstone's first team and the seed of the
`multi-agent-supervisor` blueprint. Throughout, the structured `Handoff` schema is the
highest-leverage artifact, exactly as the chapter argues.

## Planned notebooks

### 17-01 · `17-01-when-and-which-topology.ipynb` — One agent or four? Topologies and handoffs
- **Type:** concept-lab
- **Maps to:** §17.1 (🧠 organization design; the four legitimate forces and the honest
  counter-forces), §17.2 (the four topologies), §17.3 (communication, shared state, the
  `Handoff` schema).
- **Objective:** decide *whether* to split an agent and *which* topology fits — by quantifying
  the costs the demo hides (latency per hop, multiplicative reliability, lost-message risk).
- **Prereqs:** Ch 16 (reasoning patterns, `RunBudget`); Ch 8 (lost-in-the-middle / context).
- **Cell arc:**
  - 🧠 mental model: an agent is an employee (job description = system prompt, skills = tools,
    need-to-know = context/permissions); you hire only when one person genuinely can't do the job.
  - The four forces, ranked: context isolation (strongest), specialization, parallelism,
    privilege separation — each illustrated with a one-line scenario.
  - 🔮 *predict* the end-to-end reliability of three 90%-reliable stages in series — then
    compute 0.9³ = 0.73 and watch error compound across a mock pipeline.
  - The four topologies (supervisor/worker, pipeline, debate, blackboard): tiny mock of each,
    with the watch-out the table names.
  - ⚠️ pitfall: the most common multi-agent failure is a *lost message*, not a dumb agent —
    show a free-text handoff dropping the key fact, then fix it with the `Handoff` schema
    (task, context, artifacts, open_questions, done_criteria) validated at the boundary.
  - 🎯 senior lens: re-ask "would one agent with better tools and context do this more simply?"
    — the default is still the simplest design that meets the requirements.
- **Datasets/fixtures:** 2–3 in-memory "documents" + a scripted mock LLM so reliability and
  handoff-loss are deterministic and offline.
- **APIs & cost:** none/offline by design (the lesson is structural — no live calls needed).
- **You'll be able to:** justify every agent with a named force, pick a topology on purpose,
  and write a handoff that doesn't silently drop facts.

### 17-02 · `17-02-supervisor-and-specialists.ipynb` — 🔧 Build a supervisor + specialists team
- **Type:** walkthrough  *(this is the chapter's 🔧 Build, §17.5)*
- **Maps to:** §17.4 (coordination, contention, consistency — duplicated work, write
  contention, stale reads; supervisor as concurrency-control device; hierarchical budgets),
  §17.5 (🔧 Build: a supervisor and specialists for the capstone).
- **Objective:** build the §17.5 team — a supervisor that owns the goal and budget, a
  researcher wired to the RAG tool, and a writer with no retrieval — with each specialist
  exposed to the supervisor *as a tool*.
- **Prereqs:** 17-01; Ch 12 (the tool loop the supervisor *is*); Ch 16 (`RunBudget`); Ch 13
  (the `search_docs` RAG tool, mockable); Ch 15 (the handoff schema as tool input schema).
- **Cell arc:**
  - 🔧 a `Specialist` class (§17.5): a focused agent the supervisor invokes like a tool;
    `as_tool` exposes the handoff schema as its `input_schema`.
  - Two specialists differing only in job description and access: `researcher` (holds the RAG
    tool, must cite source ids) and `writer` (no retrieval; keeps citation markers).
  - The `supervise` loop: the Ch 12 tool loop where the "tools" are the team; delegation = a
    tool call; results integrate back.
  - Context isolation made visible: print what each specialist actually sees — only its
    handoff, never the supervisor's full context (retrieval noise stays out of the writer).
  - 🔮 *predict* what happens when the supervisor under-specifies a handoff (specialists share
    no memory) — then see the worker solve adjacent-X, and fix it with a richer `context`.
  - Hierarchical budget: the same `RunBudget` threaded through supervisor *and* specialists so
    one runaway worker can't consume the run; ⚠️ propagate budgets down the tree.
  - Coordination notes (§17.4): why the supervisor topology *is* a concurrency-control device —
    serialize conflicting writes through one owner; make worker tasks idempotent.
  - 🎯 senior lens: trace every hop and eval per-role (Ch 22/23) — you can't fix the team if
    you can't see which member failed.
  - Closes pointing at the blueprint: "you built the 60-line version; here's the real one."
- **Datasets/fixtures:** a tiny doc set in `data/` for the mock RAG tool; mock LLM returns
  canned researcher findings and a writer draft so the team runs free and deterministically.
- **APIs & cost:** mockable (`MOCK=1` scripts the supervisor's delegations + specialist
  outputs); live ≈ a few supervisor turns plus one call per specialist invocation.
- **You'll be able to:** stand up a bounded supervisor/worker team with structured handoffs and
  context isolation — the capstone's first multi-agent slice.

## Feeds (cross-pillar)
- **Blueprint(s):** the §17.5 team is the toy version of
  [`blueprints/multi-agent-supervisor/`](../../../blueprints/multi-agent-supervisor/) — typed
  handoffs, hierarchical budgets, per-role tracing, a task board with atomic claiming; 17-02
  ends by pointing here.
- **Template(s):** the `Specialist`/`Handoff` shapes feed
  [`templates/agent-project-starter/`](../../../templates/agent-project-starter/).
- **Capstone:** builds `capstone/agents/` (the supervisor + researcher + writer team);
  Chapter 18 rebuilds it with frameworks, Chapter 20 gates its risky tools, Part VII runs the
  supervisor as a Celery job behind FastAPI. Checkpoint `checkpoints/ch17-supervisor`.

## Dependencies
- Ch 16 (`RunBudget`, reasoning patterns) · Ch 12 (tool loop) · Ch 13 (`search_docs` RAG tool)
  · Ch 15 (structured handoffs). Feeds Ch 18 (same team, three frameworks) · Ch 20 (approval
  gates on the team's tools) · Ch 29 (distributed-systems framing).

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` with no errors and no live spend.
- [ ] `Specialist.as_tool`, the handoff schema, and the `supervise` loop match the book's §17.5
      code; the budget is genuinely hierarchical (supervisor + specialists).
- [ ] Context isolation and a lost/garbled-handoff pitfall are demonstrated, not just described.
- [ ] Recap + 2–4 exercises per notebook; secrets from env only; links resolve to
      `blueprints/multi-agent-supervisor/` and `capstone/agents/`.
