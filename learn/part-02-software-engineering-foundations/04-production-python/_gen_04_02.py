"""Generate 04-02-async-and-the-event-loop.ipynb (concept-lab). Throwaway builder."""
import json
from pathlib import Path

HERE = Path(__file__).parent


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(text)}


def code(text):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _lines(text),
    }


def _lines(text):
    text = text.strip("\n")
    raw = text.split("\n")
    return [ln + "\n" for ln in raw[:-1]] + [raw[-1]]


cells = []

cells.append(md(r"""
# Concurrency Without Freezing the Loop

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 4 §4.3 · type: concept-lab*

**The promise:** by the end you can run many I/O-bound tasks concurrently with `asyncio`, **bound** the fan-out, and instantly recognize the one mistake — a blocking call — that stalls every request on a server.

Runs fully **offline and free**: a tiny async sleep/echo "service" stands in for the network, so the timings are real but no packets leave your machine. No API key, nothing billed.
"""))

cells.append(md(r"""
## 🧠 Why this matters

Agent backends are overwhelmingly **I/O-bound**: they wait on model APIs, vector databases, and tool calls over HTTP. While one request waits two seconds for a model, your server should be serving hundreds of others. That is **concurrency** — making progress on many tasks by interleaving their waits — and `asyncio` is Python's way of doing it on a single thread.

This is the mental model behind every later agent backend in the book. The capstone's tool loop fans out model calls, the RAG pipeline fetches and embeds concurrently, FastAPI (Chapter 25) serves requests on this exact event loop. Two ideas carry all of it: **bounded fan-out** (concurrency with a cap) and **never block the loop**. Get those wrong and a single synchronous call freezes an entire server. See §4.3.
"""))

cells.append(md(r"""
## Objectives & prereqs

**By the end you can:**
- Explain what an `async def` coroutine and the **event loop** are, and why `await` is a suspension point.
- Run many awaitables concurrently with `asyncio.gather` and *measure* the wall-clock win.
- Cap in-flight work with an `asyncio.Semaphore` — the agent-fan-out pattern reused all book long.
- Diagnose a frozen event loop caused by a blocking call, and fix it with `asyncio.sleep` / `asyncio.to_thread`.
- Pick the right concurrency model (asyncio vs threads vs processes) from the workload.

**Prereqs:** [`04-01-mutability-typing-drills.ipynb`](04-01-mutability-typing-drills.ipynb). Standard library only (`asyncio`, `time`).

**Run first:** the Setup cell. Defaults to `MOCK=1` (here: fully offline — an async stub simulates latency).

> **Note on `await` at the top level.** Jupyter runs an event loop for you, so a cell can `await` directly. This notebook wraps each demo in `asyncio.run(...)` so it also runs identically as a plain script.
"""))

cells.append(code(r"""
# --- Setup -------------------------------------------------------------------
import asyncio
import os
import random
import time

from dotenv import load_dotenv

load_dotenv()  # reads a local .env if present; never hardcode keys

# MOCK=1 (default): an in-process async stub simulates I/O latency, so the lab is
# fully offline, free, and deterministic. There is no live network path here --
# the switch is kept for a uniform contract across every companion notebook.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(43)  # determinism for the (tiny) jitter used below

print(f"MOCK mode: {MOCK}  (offline async stub stands in for the network)")
print(f"asyncio event loop policy: {type(asyncio.get_event_loop_policy()).__name__}")
"""))

cells.append(md(r"""
## 1 · A coroutine and the event loop

An `async def` function is a **coroutine** — *calling* it builds an awaitable object but runs nothing. The **event loop** runs coroutines, and every `await` is a marked point where the coroutine pauses and the loop switches to whichever other task is ready. Cooperative multitasking, explicit at every suspension point.

Our stand-in for "a network call that takes a while" is `slow_echo`: it `await asyncio.sleep(delay)` (a *non-blocking* wait that yields to the loop), then returns. No real I/O, but the suspension behaviour is identical.
"""))

cells.append(code(r"""
async def slow_echo(label: str, delay: float = 1.0) -> str:
    # Stand-in for one I/O-bound call (a model API, a DB query, an HTTP fetch).
    # `asyncio.sleep` is the async, loop-yielding wait -- NOT time.sleep.
    await asyncio.sleep(delay)
    return f"{label} done after {delay:.2f}s"


# Calling the coroutine returns an awaitable; nothing has run yet.
coro = slow_echo("probe", 0.01)
print("type of slow_echo(...):", type(coro).__name__, "-- nothing has run yet")
coro.close()  # we built it only to inspect it; close it so it isn't left un-awaited

# asyncio.run drives the loop until the coroutine completes.
print(asyncio.run(slow_echo("probe", 0.01)))
"""))

cells.append(md(r"""
**What you just saw.** `slow_echo(...)` produced a *coroutine object* — defining work, not doing it. Only `asyncio.run(...)` (or an `await`) drove the event loop and actually executed it. That separation between *describing* async work and *running* it is the whole basis for scheduling many of them at once.
"""))

cells.append(md(r"""
## 2 · 🔮 Predict: ten 1-second tasks under `gather`

`fetch_all` launches ten `slow_echo` calls, each sleeping **1 second**, with `asyncio.gather`. `gather` schedules them all on the loop and waits for all to finish.

**Predict the wall-clock time before running:** about **10 seconds** (one after another) or about **1 second** (all overlapping their waits)?
"""))

cells.append(code(r"""
async def fetch_all(n: int = 10, delay: float = 1.0) -> list[str]:
    # gather schedules every coroutine on the loop; their waits OVERLAP.
    tasks = [slow_echo(f"task-{i}", delay) for i in range(n)]
    return await asyncio.gather(*tasks)


start = time.perf_counter()
results = asyncio.run(fetch_all(10, 1.0))
elapsed = time.perf_counter() - start

print(results[0], "...", results[-1])
print(f"\n10 tasks x 1.0s each completed in {elapsed:.2f}s wall-clock")
print("(sequential would have been ~10s; they overlapped their waits)")
"""))

cells.append(md(r"""
**What you just saw.** Ten one-second tasks finished in ~1 second, not ten. While each coroutine was parked at its `await asyncio.sleep(1)`, the loop ran the others — their *waiting* overlapped. This is the entire economic argument for async servers: thousands of cheap, mostly-waiting tasks share one thread instead of one blocking the next.
"""))

cells.append(md(r"""
## 3 · Bounded concurrency: the agent-fan-out pattern

Unbounded fan-out is a foot-gun: launch 10,000 model calls at once and you hit rate limits, exhaust memory, and melt your provider quota. The pattern you will reuse constantly is **bounded concurrency** — fan out many calls but cap how many are *in flight* with an `asyncio.Semaphore`.
"""))

cells.append(code(r"""
async def bounded_fetch(n: int, delay: float, limit: int) -> tuple[list[str], int]:
    sem = asyncio.Semaphore(limit)       # at most `limit` calls in flight at once
    in_flight = 0
    peak = 0

    async def one(i: int) -> str:
        nonlocal in_flight, peak
        async with sem:                  # acquire a slot (waits if all are taken)
            in_flight += 1
            peak = max(peak, in_flight)
            try:
                return await slow_echo(f"task-{i}", delay)
            finally:
                in_flight -= 1

    results = await asyncio.gather(*(one(i) for i in range(n)))
    return results, peak


start = time.perf_counter()
results, peak = asyncio.run(bounded_fetch(n=10, delay=1.0, limit=5))
elapsed = time.perf_counter() - start

print(f"ran 10 tasks with a cap of 5; peak concurrent = {peak}")
print(f"wall-clock = {elapsed:.2f}s  (~2 waves of 5 x 1s, so ~2s, not ~1s or ~10s)")
"""))

cells.append(md(r"""
**What you just saw.** The semaphore never let more than 5 tasks run at once, so 10 tasks ran as two waves of five — about 2 seconds. You traded a little latency for a hard ceiling on in-flight work. That ceiling is what keeps an agent fanning out tool calls from tripping rate limits or running the box out of memory; the capstone's executor and tool loop use exactly this shape.
"""))

cells.append(md(r"""
## 4 · ⚠️ Pitfall: a blocking call freezes the *entire* loop

The cardinal sin of async: a **blocking** call inside a coroutine — `time.sleep`, the sync `requests` library, a heavy pandas operation. It doesn't just slow that one task; it **freezes the whole event loop**, so *every* concurrent task stalls behind it. The loop is one thread; a synchronous call holds that thread hostage.

Below, one task uses `time.sleep(1.0)` (blocking) instead of `asyncio.sleep`. The other nine use the correct async wait.

**🔮 Predict:** with `gather` running all ten, will the total be ~1s (as before) or closer to ~2s (because the blocking task serializes itself on top of the others)?
"""))

cells.append(code(r"""
async def blocking_task(label: str) -> str:
    time.sleep(1.0)                 # WRONG: synchronous sleep holds the only thread
    return f"{label} (blocked the loop!)"


async def mixed_run() -> float:
    start = time.perf_counter()
    tasks = [blocking_task("bad")] + [slow_echo(f"good-{i}", 1.0) for i in range(9)]
    await asyncio.gather(*tasks)
    return time.perf_counter() - start


elapsed = asyncio.run(mixed_run())
print(f"one time.sleep(1) among nine asyncio.sleep(1): {elapsed:.2f}s")
print("The blocking second stops the loop dead -- nothing else makes progress")
print("while time.sleep holds the thread, so the work serializes (~2s, not ~1s).")
"""))

cells.append(code(r"""
# The fix when the work is genuinely blocking (a sync library, CPU-light I/O):
# push it OFF the loop's thread with asyncio.to_thread, so the loop stays free.
async def offloaded_task(label: str) -> str:
    await asyncio.to_thread(time.sleep, 1.0)   # runs in a worker thread
    return f"{label} (offloaded, loop stayed free)"


async def fixed_run() -> float:
    start = time.perf_counter()
    tasks = [offloaded_task("fixed")] + [slow_echo(f"good-{i}", 1.0) for i in range(9)]
    await asyncio.gather(*tasks)
    return time.perf_counter() - start


elapsed = asyncio.run(fixed_run())
print(f"with asyncio.to_thread instead of a raw time.sleep: {elapsed:.2f}s")
print("Back to ~1s: the loop kept switching because nothing blocked its thread.")
"""))

cells.append(md(r"""
**What you just saw.** The single `time.sleep` inside a coroutine dragged the whole batch to ~2s — while it held the thread, *no other task could resume*. Moving that blocking call to `asyncio.to_thread` (or using a truly async library, `asyncio.sleep` / `httpx.AsyncClient`) freed the loop and restored ~1s. This is the most common production async bug, and "why did every request get slow at once?" is its signature.
"""))

cells.append(md(r"""
## 5 · 🔮 Predict: do threads speed up a CPU-bound loop?

Concurrency is not parallelism. CPython's **GIL** (global interpreter lock) lets only one thread execute Python bytecode at a time. So before you run the next cell, **predict**: will splitting a pure-Python CPU-bound counting loop across 4 threads make it ~4× faster, about the same, or *slower*?

(The work below is deliberately small so the cell stays quick.)
"""))

cells.append(code(r"""
import threading


def cpu_burn(n: int) -> int:
    # Pure-Python CPU work: no I/O, so the GIL is held the whole time.
    total = 0
    for i in range(n):
        total += i * i
    return total


N = 2_000_000

# Sequential baseline.
start = time.perf_counter()
for _ in range(4):
    cpu_burn(N)
seq = time.perf_counter() - start

# "Parallel" with 4 threads -- but the GIL serializes Python bytecode.
start = time.perf_counter()
threads = [threading.Thread(target=cpu_burn, args=(N,)) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()
threaded = time.perf_counter() - start

print(f"sequential 4x : {seq:.3f}s")
print(f"4 threads     : {threaded:.3f}s")
print(f"speedup       : {seq / threaded:.2f}x  (NOT ~4x -- the GIL serializes CPU-bound Python)")
"""))

cells.append(md(r"""
**What you just saw.** Four threads gave roughly **no** CPU speedup (often a hair *slower*, from lock contention): the GIL let only one thread run Python bytecode at a time. Threads help when the work is **I/O-bound with a sync-only library** (the GIL is released during the actual I/O wait), but for CPU-bound Python you need **processes** (separate interpreters) or native libraries (NumPy) that release the GIL. The decision table:

| Workload | Tool | Why |
|---|---|---|
| I/O-bound, high concurrency (APIs, DBs, agents) | `asyncio` | Thousands of cheap tasks on one thread; no lock contention |
| I/O-bound, but the library is **sync-only** | threads | The GIL releases during I/O waits, so threads overlap fine |
| CPU-bound (parsing, embeddings math, image work) | processes | Separate interpreters sidestep the GIL; or use native libs (NumPy) |
"""))

cells.append(md(r"""
## 🎯 Senior lens

Agent backends live almost entirely in the **top row** of that table — they wait on models, vector stores, and tools far more than they compute. That single fact is why FastAPI (Chapter 25) and this book are **async-first**: the cheapest way to serve more concurrent users is not a bigger box, it is not blocking the loop. A senior's review reflex on any agent code is "is every I/O path async end to end, and is the fan-out bounded?" — because one stray `requests.get`, one `time.sleep`, one synchronous DB driver in a hot path silently caps the whole service's throughput at one-request-at-a-time, no matter how many workers you add.

They also resist the temptation to *parallelize the wrong thing*: reaching for threads to speed up CPU-bound Python wastes a day and yields nothing, while the real win was a process pool or pushing the math into NumPy. Match the model to the workload, and keep the loop's thread sacred.
"""))

cells.append(md(r"""
## Recap

- An `async def` is a **coroutine**: calling it builds an awaitable; the **event loop** runs it, and every `await` is a suspension point.
- `asyncio.gather` overlaps the **waits** of many I/O-bound tasks — ten 1s calls finish in ~1s, not ~10s.
- **Bound the fan-out** with an `asyncio.Semaphore`: cap in-flight calls so you don't trip rate limits or run out of memory.
- A **blocking call inside a coroutine freezes the whole loop** — fix it with `asyncio.sleep` / an async client, or push it off the thread with `asyncio.to_thread`.
- Concurrency ≠ parallelism: the **GIL** means threads don't speed up CPU-bound Python — use `asyncio` for I/O, threads for sync-I/O libraries, processes for CPU work.
"""))

cells.append(md(r"""
## Exercises

Each exercise *changes* something and asks you to predict the result first. (Solutions land in `solutions/` in Phase 2.)

1. **Tighten the cap.** Re-run `bounded_fetch(20, 1.0, limit=...)` with `limit=1`, `limit=4`, and `limit=20`. Predict the wall-clock for each *before* running, then plot the trade-off between the cap and total time. Where does raising the cap stop helping?
2. **Add timeouts.** Wrap a `slow_echo("slow", 5.0)` call in `asyncio.wait_for(..., timeout=1.0)` and predict what happens. Catch the `TimeoutError` and return a fallback string instead — the pattern every real model call needs.
3. **Survive a partial failure.** Make one task `raise ValueError`. Predict what `asyncio.gather(...)` does to the *other* tasks, then re-run with `asyncio.gather(..., return_exceptions=True)` and explain the difference for an agent fanning out tool calls.
4. **Measure the offload tax.** Time `offloaded_task` vs `slow_echo` for a batch of 50. Predict whether `to_thread` adds measurable overhead at this scale, then confirm. When is offloading worth it?
"""))

cells.append(code(r"""
# Exercise 1 -- your code here
"""))

cells.append(code(r"""
# Exercise 2 -- your code here
"""))

cells.append(code(r"""
# Exercise 3 -- your code here
"""))

cells.append(code(r"""
# Exercise 4 -- your code here
"""))

cells.append(md(r"""
## Next

- ▶️ **Next notebook:** [`04-03-packaging-errors-config.ipynb`](04-03-packaging-errors-config.ipynb) — from script to package: the `src/` layout, a typed error hierarchy, structured logging, and one validated `Settings` object — the `core/` trio the capstone is built on.
- 📖 **Book:** revisit §4.3 (async Python) and the concurrency-vs-parallelism decision table.
- 🎓 **Capstone:** this bounded-async fan-out is the concurrency model the capstone's agent loop runs on — the same pattern reappears in the plan executor (Ch 6) and the tool loop (Ch 12). FastAPI (Ch 25) serves requests on this exact event loop.
"""))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = HERE / "04-02-async-and-the-event-loop.ipynb"
out.write_text(json.dumps(nb, indent=1, ensure_ascii=True), encoding="utf-8")
print("wrote", out)
