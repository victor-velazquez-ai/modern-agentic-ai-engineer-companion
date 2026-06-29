# Ch 04 — Production Python

> Companion plan · Part II · book file `chapters/04-production-python.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Part II is software-engineering practice, so this chapter is **drills + concept-labs**, not a
build: the reader *feels* the bugs the chapter warns about (shared mutable state, a blocked
event loop) by running tiny programs that misbehave, then fixes them. The async lab is also
the mental model behind every later agent backend (bounded fan-out of model calls), and the
small `core/` config/errors/logging the book builds here is foreshadowed for the capstone.

## Planned notebooks

### 04-01 · `04-01-mutability-typing-drills.ipynb` — Names, balloons, and types that catch bugs
- **Type:** drill
- **Maps to:** book §4.1 (the language you thought you knew), §4.2 (typing seriously)
- **Objective:** predict aliasing/mutation outcomes correctly every time, and let a type
  checker catch a hallucinated attribute before the code runs.
- **Prereqs:** none (first Part II notebook; basic Python assumed).
- **Cell arc:**
  - 🧠 names-are-strings-tied-to-balloons; assignment never copies (the book's image).
  - 🔮 *predict* `b = a; b.append(4); print(a)` — then run and see the shared balloon.
  - Drill: mutable default argument `registry=[]` accumulates across calls; fix with `None`.
  - Drill: late-binding closure in a loop (all handlers call `"save"`); fix with `n=name`.
  - Mutable vs immutable as a table; why immutables are safe to share across threads/caches.
  - Typing drill: annotate `top_chunks(...) -> list[tuple[float, str]]`; run mypy on a file
    with a wrong attribute and read the error.
  - 🧠 `Protocol` (structural typing): an `LLMClient` shape that a fake satisfies with no
    inheritance — the seam used all over the book.
  - ⚠️ pitfall: "looks like it captures a value, actually captures a live reference" — the
    shared root cause of both the default-arg and closure bugs.
- **Datasets/fixtures:** none (pure in-memory values + one tiny `.py` for mypy to check).
- **APIs & cost:** none / offline (mypy or pyright runs locally; no model calls).
- **You'll be able to:** spot aliasing/late-binding traps on sight and use Protocols + a
  checker as cheap guardrails on AI-generated code.

### 04-02 · `04-02-async-and-the-event-loop.ipynb` — Concurrency without freezing the loop
- **Type:** concept-lab
- **Maps to:** book §4.3 (async Python), incl. the GIL / concurrency-vs-parallelism table
- **Objective:** run many I/O-bound tasks concurrently with `asyncio`, bound the fan-out, and
  recognize the one mistake (a blocking call) that stalls every request on a server.
- **Prereqs:** 04-01.
- **Cell arc:**
  - 🧠 coroutines + the event loop: `await` is a suspension point; cooperative multitasking.
  - Build `fetch_all` over a *mock* awaitable I/O source; 🔮 *predict* wall-clock for 10×1s
    tasks under `asyncio.gather` (≈1s, not 10s), then time it.
  - Bounded concurrency: an `asyncio.Semaphore(5)` cap — the agent-fan-out pattern reused all
    book long.
  - ⚠️ pitfall: drop a `time.sleep`/sync call into a coroutine and watch *all* tasks stall;
    fix with `asyncio.sleep` / `asyncio.to_thread`.
  - 🔮 *predict* whether threads speed up a CPU-bound loop (no — the GIL), then read the
    decision table: asyncio (I/O) vs threads (sync I/O libs) vs processes (CPU).
  - 🎯 senior lens: agent backends are dominated by the I/O-bound row — why FastAPI and this
    book are async-first.
- **Datasets/fixtures:** none — a tiny `async` sleep/echo "service" stands in for network I/O
  so the lab runs offline and deterministically.
- **APIs & cost:** none / offline (no live HTTP; an async stub simulates latency).
- **You'll be able to:** write bounded async fan-out and instantly diagnose a frozen event
  loop — the concurrency model the capstone's agent loop runs on.

### 04-03 · `04-03-packaging-errors-config.ipynb` — From script to package: structure, errors, config
- **Type:** walkthrough
- **Maps to:** book §4.4 (packaging/uv/lockfiles), §4.5 (structure & imports), §4.6 (errors,
  logging, configuration) — the chapter's 🔧 Build (`core/config.py`, `core/errors.py`,
  `core/logging.py`)
- **Objective:** lay out a `src/` package, model expected vs. unexpected failures with a typed
  exception hierarchy, log structured events, and load one validated `Settings` from the env.
- **Prereqs:** 04-01, 04-02.
- **Cell arc:**
  - Read a `pyproject.toml` (declared ranges) vs a lockfile (pinned tree); why both are
    committed; the three `uv` commands (`sync` / `add` / `run`) explained, not run live.
  - Walk the src layout and one-way dependency rule (`api → agents → tools → core`); 🔮
    *predict* why a circular import fails mid-execution, then trigger and fix it by moving a
    shared type down into `core/`.
  - 🔧 build a small `CapstoneError`/`ToolError` hierarchy; translate at a boundary with
    `raise ToolError(...) from e` and inspect the chained traceback.
  - ⚠️ pitfall: `logging` `extra={...}` fields are *silently dropped* under the default text
    formatter — wire a JSON/structured handler so `tool`/`thread_id`/`ms` actually appear.
  - 🔧 a `pydantic-settings` `Settings` that fails fast on a missing required var; secrets
    from env only, never hardcoded.
  - 📋 the chapter's production-Python checklist as a self-audit cell.
  - 🎯 senior lens: `core/` is "small, boring, and load-bearing" — every later chapter imports
    it instead of reinventing config/errors/logging.
- **Datasets/fixtures:** a throwaway in-notebook package tree (written to a temp dir) and a
  tiny `.env`-style mapping; nothing committed.
- **APIs & cost:** none / offline.
- **You'll be able to:** structure a real Python service and stand up the `core/` trio the
  capstone is built on — typed config, a clean error hierarchy, and structured logging.

## Feeds (cross-pillar)
- **Blueprint(s):** — (the async fan-out and `core/` patterns recur, but this chapter ships no
  standalone blueprint).
- **Template(s):** — (the `Settings`/`core` shape is later reused by the capstone and the
  FastAPI template, Ch 25; nothing authored here).
- **Capstone:** seeds `capstone-project/.../core/` (config, errors, logging) — the chapter's 🔧 Build;
  the bounded-async pattern reappears in the plan executor (Ch 6) and tool loop (Ch 12).

## Dependencies
- None upstream. This is the foundation Ch 5–7 and most later code assume (typing, async,
  `core/`).

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` (here: fully offline) with no errors.
- [ ] Mutability, closure, async, and import examples match the book's §4 code shapes exactly.
- [ ] The `core/` trio matches the book's `Settings` / exception-hierarchy / structured-logging
      code; the `extra`-fields pitfall is shown, not just described.
- [ ] Recap + 2–4 exercises per notebook; any config read from env only; no hardcoded secrets.
