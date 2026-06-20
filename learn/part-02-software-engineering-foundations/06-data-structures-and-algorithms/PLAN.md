# Ch 06 — Data Structures, Algorithms & Complexity (the parts that matter)

> Companion plan · Part II · book file `chapters/06-data-structures-and-algorithms.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Not interview prep — this chapter is **felt cost**. The drill makes the O(n²) "list-in-a-loop"
trap visible by timing it against the O(n) `set` fix at real scale, and builds the daily-driver
structures' reflexes. The walkthrough constructs the capstone's plan executor in embryo: a
topological-sort DAG runner that pays the graph's *depth* in latency instead of its *size* —
the trade that makes agent-platform economics work.

## Planned notebooks

### 06-01 · `06-01-big-o-and-the-daily-structures.ipynb` — Cost curves you can feel
- **Type:** drill
- **Maps to:** book §6.1 (Big-O intuition), §6.2 (the structures you use daily), §6.3
  (strings, parsing, tokenization-adjacent problems)
- **Objective:** choose the right structure by recognizing the cost curve, and stop writing
  the accidental-quadratic patterns that pass every unit test and melt in production.
- **Prereqs:** Ch 4 (Python fluency).
- **Cell arc:**
  - 🧠 the only Big-O question that matters: input grows 10×, what happens to cost? (O(1) /
    log n / n / n log n / n², in feel not formalism).
  - 🔮 *predict* the runtime gap, then time the book's two dedup loops — `id in list` (O(n²))
    vs `id in set` (O(n)) — at 100 then ~100k items; watch one melt.
  - Quadratic-suspect gallery: `+=` on strings in a loop, `list.pop(0)`/`list.remove` in a
    loop, "match two lists" with nested scans → build a `dict` first.
  - Daily drivers, each with its killer op: `dict`/`set` (O(1) lookup), `list` (append/index),
    `deque` (O(1) both ends), heap (`heapq.nlargest` top-k), tree/`bisect` (ordered/range),
    graph (dict of edges). Reproduce the book's reach-for-it table.
  - 🔧 the sliding-window `chunk(text, size, overlap)` from the chapter; probe the off-by-one
    space that hides the bugs; budget in *tokens not characters* (≈3–4 chars/token English).
  - Tolerant `extract_json` from messy model output (regex for the span, then `json.loads`).
  - ⚠️ pitfall: regex is for tokens/patterns, *not* nested structure — past one line or nested
    groups, switch to a parser.
  - 🎯 senior lens: in agent systems the costly unit is a *model call* (6 orders of magnitude
    over a dict lookup) — re-summarizing history every turn is O(n²) in *tokens*.
- **Datasets/fixtures:** generated in-cell (a list of N ids, a text blob for chunking); nothing
  committed as a binary.
- **APIs & cost:** none / offline (`time.perf_counter` timings only).
- **You'll be able to:** pick among the six structures correctly and catch quadratic blowups by
  eye before real data finds them.

### 06-02 · `06-02-plan-executor-topo-sort.ipynb` — 🔧 Run a task DAG (the plan executor in embryo)
- **Type:** walkthrough  *(this is the chapter's 🔧 Build)*
- **Maps to:** book §6.4 (where algorithmic thinking shows up: search, ranking, scheduling) —
  the 🔧 Build (`run_plan` over a dependency DAG)
- **Objective:** execute an agent plan expressed as a dependency dict, running every ready
  batch concurrently, in latency equal to the graph's depth — not its size.
- **Prereqs:** 06-01; Ch 4 async (`gather`, the bounded `Semaphore`).
- **Cell arc:**
  - 🧠 three classics in production clothes: vector search = nearest-neighbor (exact O(n) vs
    ANN/HNSW sub-linear); ranking = heaps + merge ("best k of many"); scheduling = topo-sort.
  - Model a plan as `deps: dict[str, set[str]]` (e.g. `{"draft": {"research"}, ...}`).
  - 🔧 build `run_plan` with `graphlib.TopologicalSorter`: `prepare → while is_active →
    get_ready (batch) → await gather(run_task) → done`.
  - 🔮 *predict* wall-clock for a 12-task plan: sequential (12 latencies) vs batched-by-depth
    (≈3–4) — then run a mock `run_task` (an async sleep) and confirm.
  - Add the bounded-concurrency `Semaphore` from Ch 4 so wide ready-batches don't stampede.
  - ⚠️ pitfall: a dependency *cycle* — `prepare()` raises; show the failure and why DAGs must
    be acyclic.
  - 🎯 senior lens: a planner that serializes independent subtasks pays the graph's size in
    latency; correctness comes from the topo order, speed from `gather`.
  - 📋 the complexity-&-structures checklist as a self-audit; close by pointing at where Part V
    multi-agent orchestration reuses this exact core.
- **Datasets/fixtures:** an in-cell example DAG; a mock async `run_task` (sleep + record order)
  so it runs offline and deterministically.
- **APIs & cost:** none / offline (no model calls; `run_task` is a timed stub).
- **You'll be able to:** turn a dependency dict into a concurrent, cycle-checked executor — the
  scheduling core the capstone's multi-agent orchestration is built on.

## Feeds (cross-pillar)
- **Blueprint(s):** — (the top-k/heap and DAG patterns recur in retrieval and orchestration
  blueprints, but are authored there).
- **Template(s):** —
- **Capstone:** seeds the capstone's plan executor / scheduling core (the `run_plan` +
  bounded-`Semaphore` pattern Part V's multi-agent orchestration builds on); the `chunk`
  skeleton reappears in `capstone/.../rag/` (Ch 13).

## Dependencies
- Ch 4 (async `gather` + `Semaphore`). Forward links: Ch 13 (chunking/ANN search), Ch 17
  (multi-agent orchestration reuses the DAG executor).

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` (offline) with no errors; timings are small.
- [ ] `chunk`, the dedup drill, and `run_plan` match the book's §6 code exactly (incl. the
      cycle-raises-on-`prepare` behavior).
- [ ] Each notebook ends with recap + 2–4 exercises; no committed binary fixtures.
- [ ] The "model call is the costly unit" framing is present and tied to the timings shown.
