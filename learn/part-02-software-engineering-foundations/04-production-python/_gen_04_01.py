"""Generate 04-01-mutability-typing-drills.ipynb (drill). Throwaway builder."""
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
# Names, Balloons, and Types that Catch Bugs

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 4 §4.1–4.2 · type: drill*

**The promise:** by the end you can predict every aliasing and late-binding outcome on sight, and let a type checker catch a hallucinated attribute *before* the code runs.

This is the first notebook in Part II. It runs fully **offline and free** — pure in-memory Python plus one optional local type-checker pass. No API key, nothing billed.
"""))

cells.append(md(r"""
## 🧠 Why this matters

In Python, *variables are not boxes; they are names bound to objects.* Assignment never copies. `b = a` ties a second name to the **same** object, so if that object is mutable, a change through either name is visible through both. Picture objects as balloons floating in memory and names as strings tied to them — most "spooky action at a distance" bugs are someone mutating a balloon you didn't know you shared.

This is not academic. AI-generated Python is fluent and plausible and wrong in *exactly* these ways: a mutable default that accumulates state across calls, a closure in a loop that captures a live reference instead of a value. You cannot review what you do not deeply understand. Type hints are your cheapest guardrail against the second failure mode — a checker catches a hallucinated attribute on a typed signature before a single line executes. See §4.1–4.2.
"""))

cells.append(md(r"""
## Objectives & prereqs

**By the end you can:**
- Predict aliasing and mutation outcomes (`b = a; b.append(...)`) every time.
- Spot the two classic reference traps — the mutable default argument and the late-binding closure — and apply the standard fix to each.
- Use a `Protocol` for *structural* typing: a fake satisfies an interface with no inheritance.
- Run `mypy` on a file with a hallucinated attribute and read the error it reports.

**Prereqs:** none — this is the first Part II notebook; basic Python is assumed.

**Packages:** the standard library only. The optional type-check cell shells out to `mypy` *if* it is installed; it is skipped cleanly otherwise.
"""))

cells.append(code(r"""
# --- Setup -------------------------------------------------------------------
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads a local .env if present; never hardcode keys

# This drill is pure local computation, so MOCK=1 (the default) simply means
# "fully offline" — there is no live path here. The switch is kept for a uniform
# contract across every companion notebook.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(4)  # determinism for anything stochastic (kept for the contract)

print(f"MOCK mode: {MOCK}  (this notebook is offline either way)")
print(f"python: {sys.version.split()[0]}")
print(f"mypy available: {shutil.which('mypy') is not None}")
"""))

cells.append(md(r"""
## 1 · Assignment never copies

`b = a` does not copy the list. It gives one list two names. Mutating through one name is visible through the other — that is the whole game.
"""))

cells.append(md(r"""
### 🔮 Predict

Below, `b = a`, then `b.append(4)`. Before you run it, **predict**: what does `print(a)` show — `[1, 2, 3]` or `[1, 2, 3, 4]`?
"""))

cells.append(code(r"""
a = [1, 2, 3]
b = a            # b names the SAME list -- no copy happened
b.append(4)
print("a is:", a)
print("a is b? ", a is b)   # identity: same balloon, two strings
"""))

cells.append(md(r"""
**What you just saw.** `a` is `[1, 2, 3, 4]`: there was only ever **one** list. `a is b` is `True` — same object, two names. *Rebinding* is different: `b = [9]` would move the name `b` to a fresh balloon and leave `a` untouched. Mutation changes the shared balloon; rebinding moves a name. When you actually want a copy, ask for one (`b = a.copy()` or `b = list(a)`).
"""))

cells.append(md(r"""
## 2 · Drill: the mutable default argument

A default value is evaluated **once**, at function-definition time, and then shared by every call. A mutable default (`registry=[]`) therefore accumulates state across calls — the single most common "surprise" bug in Python.
"""))

cells.append(md(r"""
### 🔮 Predict

`register("search")` then `register("fetch")`, each *without* passing a registry. Predict the second call's return value: `["fetch"]` or `["search", "fetch"]`?
"""))

cells.append(code(r"""
def register_buggy(tool, registry=[]):       # ONE list, shared by every call
    registry.append(tool)
    return registry

print("call 1:", register_buggy("search"))
print("call 2:", register_buggy("fetch"))    # surprise: the list persisted
# The default lives ON the function object, created ONCE at definition time:
print("the shared default list:", register_buggy.__defaults__[0])
"""))

cells.append(code(r"""
# The correct idiom: default to None, build a fresh list inside the body.
def register(tool, registry=None):
    registry = registry if registry is not None else []
    registry.append(tool)
    return registry

print("call 1:", register("search"))   # ['search']
print("call 2:", register("fetch"))    # ['fetch']  -- independent every time
"""))

cells.append(md(r"""
**What you just saw.** `register_buggy` kept appending to the *one* list created when the function was defined, so the second call returned `["search", "fetch"]`. The `None`-default version makes a new list per call, which is almost always what you meant. A linter (Chapter 7) flags the mutable-default case automatically; understanding is what lets you trust the fix.
"""))

cells.append(md(r"""
## 3 · Drill: the late-binding closure

A closure captures the enclosing **variable**, not its value at capture time. Create functions in a loop and they all read the variable's *final* value — a classic agent-platform bug when registering handlers or tools in a loop.
"""))

cells.append(md(r"""
### 🔮 Predict

Three lambdas are built in a loop over `["search", "fetch", "save"]`, each "remembering" `name`. Predict what `handlers["search"]()` returns after the loop finishes: `"search"` or `"save"`?
"""))

cells.append(code(r"""
def call_tool(name):
    return f"calling {name!r}"

handlers_buggy = {}
for name in ["search", "fetch", "save"]:
    handlers_buggy[name] = lambda: call_tool(name)   # captures the VARIABLE name

print("search ->", handlers_buggy["search"]())   # all three read the final 'save'
print("fetch  ->", handlers_buggy["fetch"]())
print("save   ->", handlers_buggy["save"]())
"""))

cells.append(code(r"""
# The fix: bind the value NOW via a default argument captured at definition time.
handlers = {}
for name in ["search", "fetch", "save"]:
    handlers[name] = lambda n=name: call_tool(n)     # n is bound per iteration

print("search ->", handlers["search"]())
print("fetch  ->", handlers["fetch"]())
print("save   ->", handlers["save"]())
"""))

cells.append(md(r"""
**What you just saw.** Every buggy lambda printed `"save"` — they share one live variable `name`, whose value after the loop is its last element. The `n=name` default snapshots the value at each iteration, so each handler keeps its own. This is the same root cause as the mutable default: code that *looks* like it captured a value actually holds a reference that keeps living.
"""))

cells.append(md(r"""
## 4 · Mutable vs immutable, and why it matters for sharing

Whether sharing is safe comes down to one property: can the object be changed in place?

| Category | Types | Safe to share freely? |
|---|---|---|
| **Mutable** | `list`, `dict`, `set`, most custom objects | No — a change through any reference is visible through all |
| **Immutable** | `int`, `str`, `tuple`, `frozenset`, `bytes` | Yes — across functions, threads, and caches |

Immutable objects are safe to use as dict keys, to cache, and to pass between threads precisely because nobody can mutate them out from under you. The cell below proves the distinction.
"""))

cells.append(code(r"""
# Immutable: "changing" a tuple actually rebinds to a new object (different id).
t = (1, 2, 3)
before = id(t)
t = t + (4,)             # NOT in-place: a brand-new tuple
print("tuple rebinds to a new object:", id(t) != before)

# Mutable: a list mutates in place (same id), so aliases see the change.
xs = [1, 2, 3]
before = id(xs)
xs.append(4)
print("list mutated in place (same object):", id(xs) == before)

# Why immutables make safe dict keys / cache keys: they can't change their hash.
cache = {("user", 7): "Ada"}
print("immutable tuple as a key:", cache[("user", 7)])
try:
    {["user", 7]: "nope"}        # a list key -> TypeError: unhashable
except TypeError as exc:
    print("list as a key ->", type(exc).__name__, "(mutable, unhashable)")
"""))

cells.append(md(r"""
**What you just saw.** The tuple "update" produced a new object (its `id` changed); the list mutated in place (same `id`). That is exactly why immutables are safe to share and to use as keys — their identity and hash never shift under you — while a mutable shared across a boundary is a latent bug.
"""))

cells.append(md(r"""
## 5 · Typing drill: annotate a real signature

Modern syntax (Python 3.12) is clean: builtin generics, the `|` union, and PEP 695 generics with no `TypeVar` ceremony. Annotate the retrieval helper the book uses, then confirm a correct call type-checks in your head before a checker ever runs.
"""))

cells.append(code(r"""
def top_chunks(
    query: str,
    chunks: list[str],
    k: int = 5,
) -> list[tuple[float, str]]:
    # Return the top-k (score, chunk) pairs for a query. (Toy keyword scorer.)
    scored = [(float(len(set(query.split()) & set(c.split()))), c) for c in chunks]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:k]


result = top_chunks("agent tool call", ["the agent called a tool", "unrelated text"], k=1)
print(result)            # [(score, chunk)] -- matches the -> list[tuple[float, str]] hint
print("signature:", top_chunks.__annotations__)
"""))

cells.append(md(r"""
The annotation is documentation that cannot drift from the code, and it is what a checker enforces. Next we let `mypy` catch a hallucinated attribute — the failure mode you most want to catch in AI-generated code.
"""))

cells.append(md(r"""
### 🔮 Predict

The throwaway file below builds a `(score, chunk)` pair and then reads `.upper()` on the **score** (a `float`). Floats have no `.upper()`. Predict: will `mypy` flag this *before* the code runs, and roughly what will it say?
"""))

cells.append(code(r"""
# Write a tiny module with a deliberate type error and run mypy on it (if present).
SNIPPET = "\n".join([
    "def top_chunks(query: str, chunks: list[str], k: int = 5) -> list[tuple[float, str]]:",
    "    return [(1.0, c) for c in chunks][:k]",
    "",
    "best = top_chunks('q', ['a', 'b'])[0]   # best: tuple[float, str]",
    "score = best[0]                          # score: float",
    "print(score.upper())                     # BUG: float has no .upper()",
])

tmpdir = Path(tempfile.mkdtemp(prefix="typedrill_"))
modfile = tmpdir / "retrieval.py"
modfile.write_text(SNIPPET, encoding="utf-8")

if shutil.which("mypy"):
    proc = subprocess.run(
        [sys.executable, "-m", "mypy", "--no-color-output", str(modfile)],
        capture_output=True, text=True,
    )
    print(proc.stdout or proc.stderr)
else:
    print("mypy not installed -- here is the error it WOULD report:")
    print('retrieval.py:6: error: "float" has no attribute "upper"  [attr-defined]')
    print("Found 1 error in 1 file (checked 1 source file)")

shutil.rmtree(tmpdir, ignore_errors=True)
"""))

cells.append(md(r"""
**What you just saw.** The checker reported `"float" has no attribute "upper"` *without running the file*. That is the entire value proposition of typing as a guardrail: when a model hallucinates `.upper()` on a numeric field, the type checker rejects it at review time instead of you discovering it from a `3 a.m.` traceback.
"""))

cells.append(md(r"""
## 6 · 🧠 `Protocol`: structural typing and the seam used all over the book

A `Protocol` defines a *shape*. Anything with matching methods satisfies it — **no inheritance required**. This is how the book decouples business logic from a vendor: depend on the shape (`LLMClient`), not on Anthropic or OpenAI. A fake satisfies the protocol just by having the right method, which is what makes tests fast and offline.
"""))

cells.append(code(r"""
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str: ...


class FakeLLM:                       # note: does NOT inherit from LLMClient
    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
        return f"[fake answer to {prompt[:30]!r}]"


def summarize(text: str, llm: LLMClient) -> str:
    return llm.complete(f"Summarize:\n\n{text}", max_tokens=400)


# FakeLLM structurally satisfies LLMClient -> this type-checks and runs offline.
print(summarize("a long document about agents", FakeLLM()))
print("inherits from LLMClient?", LLMClient in type(FakeLLM()).__mro__)  # False -- structural, not nominal
"""))

cells.append(md(r"""
**What you just saw.** `FakeLLM` never inherited from `LLMClient`, yet `summarize` accepts it because it has the right method *shape*. A type checker verifies that structurally. This one idea — program against a protocol, swap a real client for a fake — is the seam the whole book (and the capstone's `llm/` layer) is built on; Chapter 5 grows a full pattern vocabulary on top of it.
"""))

cells.append(md(r"""
## ⚠️ Pitfall: "looks like it captures a value, actually captures a live reference"

The mutable-default bug and the late-binding-closure bug are the *same* bug wearing two costumes: code that appears to snapshot a value is really holding a reference that keeps mutating.

- A `def f(x, acc=[])` default is one object created at definition time, shared by every call.
- A `lambda: use(name)` built in a loop reads the loop variable's *current* value, not the value when the lambda was made.

**The reflex:** whenever a function is *created inside a loop*, or a default argument is *mutable*, stop and ask "value or reference?" The fixes are mechanical — `=None` then build inside, and `n=name` to bind now — but only this mental model tells you *when* to apply them.
"""))

cells.append(md(r"""
## 🎯 Senior lens

A senior treats type annotations as the **cheapest architecture documentation that exists**. Reading `def plan(goal: str, memory: MemoryStore, tools: ToolRegistry) -> Plan`, they learn the component's dependencies and contract in one line without reading the body — and when reviewing a thousand lines of AI-generated code, the typed signatures are the skeleton they check first. If the shapes are wrong, the body doesn't matter.

They also reach for `Protocol` *before* an abstract base class. Structural typing keeps the dependency arrow pointing at a shape you own rather than a vendor's concrete client, so swapping providers, or dropping in a fake for a test, is a one-line change instead of a refactor. Small, boring, decoupled — and a type checker in CI turns all of it from a hope into a gate.
"""))

cells.append(md(r"""
## Recap

- **Assignment never copies.** `b = a` makes one object with two names; mutation is shared, rebinding is not. Ask for a copy when you want one.
- **Mutable default arguments** are evaluated once and shared across calls — default to `None` and build inside.
- **Late-binding closures** capture the variable, not its value — bind the value now with `n=name`.
- Both bugs share one root cause: a live reference masquerading as a captured value.
- **Immutables are safe to share** (and to use as keys); mutables shared across boundaries are latent bugs.
- **Typing + a checker** is a cheap guardrail: `mypy`/`pyright` catch a hallucinated attribute before runtime, and a **`Protocol`** decouples your code from any concrete vendor.
"""))

cells.append(md(r"""
## Exercises

Each exercise *changes* something and asks you to predict the result first. (Solutions land in `solutions/` in Phase 2.)

1. **Copy depth.** Build `outer = [[1, 2], [3, 4]]`, then `shallow = outer.copy()` and `shallow[0].append(99)`. Predict whether `outer[0]` changed, then run it. What does this tell you about when `.copy()` is *not* enough, and which stdlib function fixes it?
2. **Spot the default.** Write a `make_counter(start=0)` factory whose returned function increments and returns a running count. Now write a *buggy* version that accidentally shares state across counters via a mutable default, predict the failure, and fix it.
3. **Loop of partials.** Rebuild the handler dict using `functools.partial(call_tool, name)` instead of a lambda. Predict whether `partial` has the late-binding problem, then confirm. Why does it behave differently from the bare lambda?
4. **Grow the protocol.** Add an `async def complete_async(...)` method to `LLMClient` and a `FakeLLM` that implements *only* the sync method. Predict what a type checker says when you pass that fake where the async method is required, then (if you have `mypy`) confirm.
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

- ▶️ **Next notebook:** [`04-02-async-and-the-event-loop.ipynb`](04-02-async-and-the-event-loop.ipynb) — the concurrency model every later agent backend runs on: bounded async fan-out, and the one blocking call that freezes the whole event loop.
- 📖 **Book:** revisit §4.1 (the language you thought you knew) and §4.2 (typing seriously).
- 🎓 **Capstone:** the `Protocol` seam here is how the capstone's `core/` and `providers/` (Ch 5) stay vendor-agnostic; typed signatures are the contract every later part imports against.
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

out = HERE / "04-01-mutability-typing-drills.ipynb"
out.write_text(json.dumps(nb, indent=1, ensure_ascii=True), encoding="utf-8")
print("wrote", out)
