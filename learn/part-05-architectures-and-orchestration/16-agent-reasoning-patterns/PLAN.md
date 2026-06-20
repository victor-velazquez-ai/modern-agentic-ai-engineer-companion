# Ch 16 — Agent Reasoning Patterns

> Companion plan · Part V · book file `chapters/16-agent-reasoning-patterns.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Chapter 12 gave the reader the raw tool loop; this chapter wraps *strategy* around it. The
notebooks turn the chapter's catalog of patterns — ReAct, plan-and-execute, reflection,
verification, routing — into small, runnable **walkthroughs** the reader can feel the
trade-offs of: each pattern is built in isolation against the same mock task so the cost,
latency, and quality differences are visible, not asserted. The third notebook is the one the
chapter insists on hardest: a hands-on `RunBudget` that makes **termination an enforced
property** (caps, deadlines, repeated-action detection) so no loop here can run away. All four
primitives — generate, act, evaluate, branch — are named and traced.

## Planned notebooks

### 16-01 · `16-01-react-and-interleaved-thinking.ipynb` — ReAct, traced step by step
- **Type:** walkthrough
- **Maps to:** §16.1 (the four primitives: generate/act/evaluate/branch), §16.2 (🧠 ReAct:
  reason–act–observe), §16.2 interleaved thinking and tool use.
- **Objective:** build the modern ReAct loop (the Ch 12 tool loop + an iterate-deliberately
  prompt) and watch it choose each action with everything observed so far in view.
- **Prereqs:** Ch 12 tool loop (`learn/part-04-.../12-02-tool-loop-from-scratch`); Ch 9
  (reasoning/thinking budget); Ch 11 (model APIs).
- **Cell arc:**
  - 🧠 mental model: a reasoning pattern is a *control-flow design*; decompose any pattern into
    generate / act / evaluate / branch.
  - Setup: `load_dotenv()`, `MOCK` switch, env check; one tiny search-ish tool + `run_tool`.
  - Build the `react_agent` loop from §16.2 (thought → tool_use → observation → repeat).
  - 🔮 *predict* whether the model answers or asks for the tool on a 2-hop question, then run.
  - Trace each turn: print thought, action, observation; show the loop's `max_steps` exit.
  - Interleaved thinking: carry thinking blocks forward across turns vs throwing them away —
    contrast the two and note the per-step thinking cost dial (§16.2).
  - ⚠️ pitfall: a tool that returns 10k tokens of raw JSON drowns the next thought — shape
    tool results (trim/summarize) as the pattern's main quality lever.
  - 🎯 senior lens: spend deep thinking only on the hard fork/surprising result, not every hop.
- **Datasets/fixtures:** 2–3 tiny in-memory "documents" so the tool is offline and deterministic.
- **APIs & cost:** mockable (`MOCK=1` returns canned tool-use blocks + a final answer); live ≈
  a short multi-step run (a handful of calls).
- **You'll be able to:** implement ReAct from scratch, read its trace, and explain when its
  adaptivity helps vs when its myopia hurts.

### 16-02 · `16-02-plan-execute-reflect-verify.ipynb` — Planning, reflection, and the verification ladder
- **Type:** walkthrough
- **Maps to:** §16.3 (plan-and-execute, replanning, task decomposition), §16.4 (reflection,
  self-critique, verification — 🔑 the verification ladder), §16.5 (router/orchestrator).
- **Objective:** layer planning and self-checking on top of ReAct, and rank exit conditions so
  the agent stops on *checkable* evidence, not vibes.
- **Prereqs:** 16-01; Ch 15 (structured outputs — the `Plan` schema); Ch 14 (keeping notes small).
- **Cell arc:**
  - Plan-and-execute: a `Plan` (Pydantic, §16.3) decomposes the task into 3–7 checkable steps;
    each step is a short bounded ReAct run; `notes` stay small (Ch 14).
  - ⚠️ pitfall: plans go stale — show a step's result invalidating step 4, then *replan*
    (coarse cadence, not every step).
  - Task-decomposition drill: rewrite a vague step ("research the market") into a concrete,
    verifiable one ("list the top five competitors with pricing pages").
  - `reflect_loop` (§16.4): critique → revise → `ACCEPT`; cap the rounds.
  - 🔮 *predict* whether self-critique improves a deliberately flawed draft — then see it also
    risk "fixing" something that was fine (shared blind spots, oscillation).
  - 🔑 the verification ladder: hard verification (run tests / validate schema) > grounded
    critique (judge + sources) > bare self-reflection; make the exit condition trustworthy.
  - Router (§16.5): a cheap `claude-haiku-4-5` classifier over a fixed label set, failing safe
    to `handoff_human` on any unknown label.
  - 🎯 senior lens: code-orchestrator (known decomposition) vs model-orchestrator (varies per
    request) — and why that distinction sets up Chapter 17.
- **Datasets/fixtures:** one short task with a verifiable artifact (e.g. a small function whose
  tests can run locally) so "hard verification" is real, not narrated.
- **APIs & cost:** mockable (canned plans, critiques, route labels); live ≈ a planner call plus
  a few short executor/critique calls.
- **You'll be able to:** decompose a task into checkable steps, add a capped reflection cycle,
  and pick the strongest available exit condition for a loop.

### 16-03 · `16-03-runbudget-and-termination-guards.ipynb` — Bounding the loop: budgets, caps, no-progress
- **Type:** walkthrough  *(the chapter's hard guardrail — ⚠️ termination / runaway cost)*
- **Maps to:** §16.6 (context engineering for long-horizon agents), §16.7 (loops, runaway
  costs, termination guarantees — the `RunBudget`), §16.8 (failure-mode taxonomy as a checklist).
- **Objective:** make termination a *provable* property of an agent run — step, token, dollar,
  and wall-clock caps plus repeated-action detection — enforced by code, never the prompt.
- **Prereqs:** 16-01 (a loop to bound); 16-02 (patterns that each contain a loop).
- **Cell arc:**
  - ⚠️ the canonical incident: an agent retries a failing call overnight; because each retry
    re-sends the growing context, cost grows *quadratically* and the billing alert finds it.
  - Build `RunBudget` from §16.7: `charge()` + `raise_if_spent()` with `max_steps`,
    `max_tokens`, `max_seconds`, `max_repeats`; `BudgetExceeded` on trip.
  - Wire it into the 16-01 ReAct loop so every turn must consume from the budget.
  - 🔮 *predict* which cap fires first on a deliberately looping mock tool — then watch
    no-progress detection catch "same tool + same hashed args" repeats.
  - Fail *well*: on a trip, checkpoint run state (Ch 14), return a partial result with a
    stop-reason, and emit metrics (steps/tokens/dollars/stop_reason) for Ch 23 dashboards.
  - Context-engineering primer (§16.6): compaction, external notes, sub-agent offloading,
    retrieval of own history, structured state at the window edges — demoed on a tiny
    transcript to show "curate, don't append".
  - 📋 walk the §16.8 failure-mode taxonomy: for ~3 rows, name *what detects it* and *what
    bounds it* (runaway loop, no-progress action, premature success).
  - 🎯 senior lens: termination is architectural — "this agent cannot spend more than $0.40 or
    60s per request, by construction" is what makes an agent deployable.
- **Datasets/fixtures:** a mock tool that intentionally never makes progress; a tiny synthetic
  transcript for the context-engineering demo (generated in-cell, not committed).
- **APIs & cost:** none/offline by design (a fake model fn lets the budget logic be tested
  deterministically and free); optional live path mirrors 16-01.
- **You'll be able to:** drop an enforced budget into any loop in this Part, detect runaway
  signatures, and answer "what are the provable bounds on this run?" in a design review.

## Feeds (cross-pillar)
- **Blueprint(s):** the `RunBudget` + termination guards seed
  [`blueprints/agent-loop/`](../../../blueprints/agent-loop/) (production loop hardening); the
  router/orchestrator sketch foreshadows
  [`blueprints/multi-agent-supervisor/`](../../../blueprints/multi-agent-supervisor/) (Ch 17).
- **Template(s):** the bounded-loop + tier-aware execution defaults flow into
  [`templates/agent-project-starter/`](../../../templates/agent-project-starter/).
- **Capstone:** `RunBudget` becomes the hierarchical budget every `capstone/agents/` run
  consumes (Ch 17 makes it tree-shaped); checkpoint `checkpoints/ch16-runbudget`.

## Dependencies
- Ch 12 (tool loop) · Ch 9 (reasoning/thinking budget) · Ch 15 (`Plan`/structured outputs) ·
  Ch 14 (context, checkpoints, notes). Feeds Ch 17 (supervisor reuses `RunBudget`), Ch 20
  (escalation reuses the verification ladder), Ch 23 (stop-reason metrics).

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` with no errors and no live spend.
- [ ] The ReAct loop, `Plan` schema, verification ranking, and `RunBudget` match the book's
      §16 code shapes (caps, `raise_if_spent`, repeated-action signature).
- [ ] Every loop in the notebooks is externally bounded; 16-03 demonstrates a trip and a
      fail-well path (checkpoint + partial result + metrics).
- [ ] Recap + 2–4 exercises per notebook; secrets from env only; links resolve to
      `blueprints/agent-loop/` and Ch 17.
