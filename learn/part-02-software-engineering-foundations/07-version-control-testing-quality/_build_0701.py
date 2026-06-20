import json, os

DIR = os.path.dirname(os.path.abspath(__file__))

def md(text):
    lines = text.split("\n")
    src = [l + "\n" for l in lines[:-1]] + ([lines[-1]] if lines[-1] != "" else [])
    return {"cell_type": "markdown", "metadata": {}, "source": src}

def code(text):
    lines = text.split("\n")
    src = [l + "\n" for l in lines[:-1]] + ([lines[-1]] if lines[-1] != "" else [])
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": src}

cells = []

cells.append(md(
"""# Testing a system with a model in it

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 07 §7.2–7.3 · type: drill*

**One-line promise:** unit-test agent logic at millisecond speed with a `FakeLLM`, mock the model's *contract* at the HTTP boundary, and learn — by reps — exactly where the line sits between a CI test and an eval."""
))

cells.append(md(
"""## 🧠 Why this matters

Your product has a non-deterministic component bolted into the middle of it: a model. That single fact breaks the naive instinct to `assert output == "expected"`. The move that saves you isn't a testing trick, it's **architectural** — split the *deterministic shell* (routing, parsing, budget checks, tool dispatch) from the *probabilistic core* (does the model answer well?), then test each with the right instrument.

The shell is ordinary code: test it exhaustively and fast with a **fake model you control**. The core's *quality* is an **eval** (Ch 22), not a red/green CI test. This drill turns that split, plus the `FakeLLM` fixture, into muscle memory — and shows the failure modes (a green test that ran nothing; a mock that breaks on every SDK release) that bite engineers who skip the reps."""
))

cells.append(md(
"""## Objectives & prereqs

**By the end you can:**
- Build the book's `FakeLLM` (scripted replies, records prompts) and wire it in as a `pytest` fixture.
- Assert on **structure** (`action.tool == "search"`, `"Oslo" in prompts[0]`) instead of exact strings.
- Spot the `pytest-asyncio` "collected but never awaited" trap and fix it.
- `parametrize` a table of edge cases, `monkeypatch` an env var, and mock a `429` retry at the HTTP boundary.
- State a property-based invariant that actually holds (coverage, not reconstruction) and read a shrunk counterexample.
- Draw the line: deterministic logic -> unit test; model quality -> eval.

**Prereqs:** Ch 4 (async) and Ch 5 (the injected `LLMProvider` seam — testability is a *design* property earned at construction, not bolted on later). No API key, no network: everything here runs offline."""
))

cells.append(code(
'''# --- Setup: imports, env, and the MOCK switch ---------------------------------
# stdlib + pytest (in requirements.txt). `respx` and `hypothesis` are OPTIONAL
# extras used in two sections; if absent we fall back to a tiny offline stand-in,
# so the notebook ALWAYS runs top-to-bottom in MOCK mode with no key, no network.
#
#   pip install respx hypothesis      # optional, to run the "live-shape" cells
import os
import json
import asyncio
import random

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# This notebook is offline by design: a FakeLLM + a fake HTTP transport exercise
# every path for free. MOCK=0 changes nothing here — there is no live model call.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"
random.seed(7)  # any sampling below is reproducible

HAS_RESPX = False
try:
    import respx  # noqa: F401
    import httpx  # respx intercepts httpx traffic
    HAS_RESPX = True
except ImportError:
    pass

HAS_HYPOTHESIS = False
try:
    from hypothesis import given, strategies as st  # noqa: F401
    HAS_HYPOTHESIS = True
except ImportError:
    pass

print(f"MOCK mode      : {MOCK}")
print(f"respx present  : {HAS_RESPX}      (HTTP-contract section uses a fallback if False)")
print(f"hypothesis     : {HAS_HYPOTHESIS}      (property section uses a fallback if False)")'''
))

cells.append(md(
"""## 1 · The pyramid is a speed strategy (§7.2)

The pyramid isn't bureaucracy; it's the harness that makes *speed* safe. Many fast **unit** tests at the base (a function, milliseconds, no network), fewer **integration** tests in the middle (your code against a real DB container), a handful of **e2e** tests on top. Cost and flakiness grow as you climb — so push every check as far *down* as it will run. Let's encode that as the lens we'll keep applying."""
))

cells.append(code(
'''PYRAMID = [
    ("unit",        "a function/class; ms; no network; a FakeLLM",  "MANY  — exhaustive"),
    ("integration", "your code vs a real Postgres/Redis container",  "FEWER — real boundaries"),
    ("e2e",         "a user flow through the deployed stack",        "FEW   — precious & slow"),
]
for layer, what, how_many in PYRAMID:
    print(f"{layer:<12} {what:<46} {how_many}")

print()
print("Rule: a check belongs at the LOWEST layer that can still catch the defect.")
print("Agent logic (routing/parsing/dispatch) is deterministic -> it lives at the base.")'''
))

cells.append(md(
"""## 2 · 🔧 Build the `FakeLLM` (§7.3)

Here's the heart of the capstone's test suite: a scripted provider that returns canned replies and **records every prompt it was sent**. It satisfies the same `LLMProvider` contract the real client does (Ch 5), so the agent can't tell the difference — which is exactly what makes the agent's logic unit-testable."""
))

cells.append(code(
'''class FakeLLM:
    """Scripted provider: returns canned replies, records every prompt.

    Matches the injected LLMProvider seam from Ch 5 (`async def complete`),
    so swapping it in is invisible to the agent under test.
    """

    def __init__(self, replies: list[str]):
        self._replies = iter(replies)
        self.prompts: list[str] = []

    async def complete(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)        # record what the agent actually sent
        return next(self._replies)         # hand back the next scripted reply


# A minimal agent + tool registry, just enough to exercise dispatch logic.
# In the capstone these are the real classes; here they're a faithful sketch.
class SearchTool:
    name = "search"

class ToolRegistry:
    def __init__(self, tools):
        self._by_name = {t.name: t for t in tools}
    def __contains__(self, name):
        return name in self._by_name
    def names(self):
        return sorted(self._by_name)

class Action:
    def __init__(self, tool, query):
        self.tool, self.query = tool, query

class Agent:
    """Deterministic shell: build a prompt, parse the model's JSON into an Action,
    validate the tool is registered. ALL of this is unit-testable with a fake."""
    def __init__(self, llm, tools: ToolRegistry):
        self.llm, self.tools = llm, tools

    async def decide(self, question: str) -> Action:
        prompt = f"Choose a tool as JSON for the question: {question}"
        raw = await self.llm.complete(prompt)
        data = json.loads(raw)                      # parsing = deterministic
        if data["tool"] not in self.tools:          # validation = deterministic
            raise ValueError(f"unregistered tool: {data['tool']}")
        return Action(tool=data["tool"], query=data.get("query", ""))

print("FakeLLM + a tiny deterministic Agent are defined.")'''
))

cells.append(md(
"""Now the test itself. In a real suite this is a `pytest` function and `llm` is a `@pytest.fixture`. We run it inline here so the notebook stays self-contained, but the **shape is the test** — note what it asserts."""
))

cells.append(code(
'''# In pytest this is:
#     @pytest.fixture
#     def llm() -> FakeLLM:
#         return FakeLLM(replies=['{"tool": "search", "query": "Oslo weather"}'])
#
#     @pytest.mark.asyncio
#     async def test_agent_dispatches_search_tool(llm):
#         ...
def make_llm() -> FakeLLM:
    return FakeLLM(replies=['{"tool": "search", "query": "Oslo weather"}'])


async def test_agent_dispatches_search_tool():
    llm = make_llm()
    agent = Agent(llm=llm, tools=ToolRegistry([SearchTool()]))
    action = await agent.decide("What is the weather in Oslo?")
    assert action.tool == "search"          # STRUCTURE, not an exact string
    assert "Oslo" in llm.prompts[0]         # the prompt carried the question
    return action, llm


action, llm = asyncio.run(test_agent_dispatches_search_tool())
print("tool dispatched :", action.tool)
print("prompt recorded :", llm.prompts[0])
print("PASS — asserted on structure + the recorded prompt, never on a brittle string.")'''
))

cells.append(md(
"""**What you just saw.** We never asserted the model's exact text. We asserted the *deterministic consequences* of its reply — which tool got dispatched, and that the question reached the prompt. That style survives a model upgrade; a golden-transcript `assert ==` would shatter on the next release."""
))

cells.append(md(
"""## 3 · ⚠️ Pitfall — the async test that runs *nothing*

This is the most dangerous failure in the whole chapter, because it's **green**. A bare `async def` test, collected by a plain pytest with no `pytest-asyncio`, is never awaited — pytest just gets a coroutine object back, doesn't run it, and reports a pass. Let's *demonstrate* it rather than just claim it."""
))

cells.append(code(
'''import warnings

# Simulate what a naive runner does: it CALLS the async test but forgets to await.
def naive_runner_collects_but_never_awaits(test_coro_fn):
    result = test_coro_fn()          # returns a coroutine; body has NOT executed
    is_coro = asyncio.iscoroutine(result)
    if is_coro:
        # Close it to avoid a "coroutine was never awaited" RuntimeWarning leaking out.
        result.close()
    return is_coro


async def test_that_should_fail():
    assert 1 == 2, "this assertion never even runs under a naive runner"


with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    never_ran = naive_runner_collects_but_never_awaits(test_that_should_fail)

print("Did the runner get an un-awaited coroutine back? ->", never_ran)
print("The assertion 1 == 2 NEVER executed, so a naive pytest reports GREEN.")
print()
print("FIX: install pytest-asyncio and either mark each test")
print("     @pytest.mark.asyncio, or set in pyproject.toml:")
print("     [tool.pytest.ini_options]")
print('     asyncio_mode = "auto"')'''
))

cells.append(code(
'''# The fix, shown for real: actually await the coroutine (what pytest-asyncio does).
async def _drive():
    try:
        await test_that_should_fail()
        return "PASS (wrong!)"
    except AssertionError as e:
        return f"FAIL (correct): {e}"

print(asyncio.run(_drive()))
print("Awaited -> the assertion runs -> the bug is caught. THAT is what the plugin buys you.")'''
))

cells.append(md(
"""## 4 · `parametrize` a table of edge cases (§7.3)

`pytest.mark.parametrize` turns one test into a table — every edge of a chunker in a few lines. We'll define a tiny chunker (it returns again in §13 RAG) and table-drive its boundaries. Inline, a parametrized test is just a loop over cases; the discipline is *enumerating the edges*."""
))

cells.append(code(
'''def chunk(text: str, size: int, overlap: int) -> list[str]:
    """Split `text` into windows of `size`, sliding by `size - overlap`.
    Small, fiddly, off-by-one-prone — exactly the code property tests love."""
    if size <= 0:
        raise ValueError("size must be positive")
    if not (0 <= overlap < size):
        raise ValueError("overlap must be in [0, size)")
    step = size - overlap
    if not text:
        return []
    return [text[i:i + size] for i in range(0, len(text), step)]


# parametrize == a table of (input, expected-property) rows.
CASES = [
    # text,      size, overlap, expected number of chunks
    ("",          4,   0,       0),     # empty -> no chunks
    ("abc",       4,   0,       1),     # shorter than a window
    ("abcd",      4,   0,       1),     # exactly one window
    ("abcdefgh",  4,   0,       2),     # clean split
    ("abcdefg",   4,   1,       3),     # overlap shrinks the step to 3
]
for text, size, overlap, expected_n in CASES:
    chunks = chunk(text, size, overlap)
    assert len(chunks) == expected_n, (text, size, overlap, chunks, "got", len(chunks))
    assert all(len(c) <= size for c in chunks)     # never oversize
print(f"All {len(CASES)} parametrized edge cases pass (each is one pytest row).")'''
))

cells.append(md(
"""And `monkeypatch` — pytest's fixture for setting an env var or attribute **with automatic cleanup** at test teardown. Inline we mimic it with a tiny context manager so you see the contract: the change is *scoped*, never leaking into the next test."""
))

cells.append(code(
'''import contextlib

@contextlib.contextmanager
def monkeypatch_env(name, value):
    """Stand-in for pytest's monkeypatch.setenv: set, then restore on exit."""
    sentinel = object()
    old = os.environ.get(name, sentinel)
    os.environ[name] = value
    try:
        yield
    finally:
        if old is sentinel:
            os.environ.pop(name, None)
        else:
            os.environ[name] = old


def read_budget() -> int:
    return int(os.getenv("AGENT_TOKEN_BUDGET", "1000"))

print("before   :", read_budget())
with monkeypatch_env("AGENT_TOKEN_BUDGET", "256"):
    print("patched  :", read_budget())          # sees the patched value
print("after    :", read_budget())              # auto-restored — no leak
print("monkeypatch's whole value is this guaranteed cleanup.")'''
))

cells.append(md(
"""## 5 · Mock the *contract* at the HTTP boundary (§7.3)

Some tests must verify behavior *at the wire*: does the client retry on a `429`? `respx` intercepts `httpx` traffic so you assert on it with **no real API, no key, no flakes**. The cell auto-falls-back to a hand-rolled fake transport when `respx` isn't installed, so it always runs."""
))

cells.append(code(
'''async def call_with_one_retry(client_get, url):
    """Tiny client policy: on a 429, retry exactly once; return the final response."""
    resp = await client_get(url)
    if getattr(resp, "status_code", 200) == 429:
        resp = await client_get(url)        # one retry on rate-limit
    return resp


if HAS_RESPX:
    import httpx
    import respx

    async def run_respx_demo():
        with respx.mock(base_url="https://api.example.test") as mock:
            route = mock.get("/v1/messages").mock(
                side_effect=[
                    httpx.Response(429, json={"error": "rate_limited"}),
                    httpx.Response(200, json={"ok": True}),
                ]
            )
            async with httpx.AsyncClient(base_url="https://api.example.test") as client:
                resp = await call_with_one_retry(client.get, "/v1/messages")
            assert route.call_count == 2          # asserted the client RETRIED
            assert resp.status_code == 200
            return route.call_count
    calls = asyncio.run(run_respx_demo())
    print(f"respx: client retried once on 429, then got 200. HTTP calls = {calls}")
else:
    # Offline fallback: a fake transport that returns 429 then 200.
    class _Resp:
        def __init__(self, status_code):
            self.status_code = status_code

    class _FakeTransport:
        def __init__(self, statuses):
            self._it = iter(statuses)
            self.call_count = 0

        async def get(self, url):
            self.call_count += 1
            return _Resp(next(self._it))

    async def run_fallback():
        t = _FakeTransport([429, 200])
        resp = await call_with_one_retry(t.get, "/v1/messages")
        assert t.call_count == 2 and resp.status_code == 200
        return t.call_count
    calls = asyncio.run(run_fallback())
    print(f"fallback transport: retried once on 429, then 200. HTTP calls = {calls}")
    print("(install respx to assert against real httpx traffic.)")'''
))

cells.append(md(
"""> ⚠️ **Pitfall — mock what you *own*, not vendor internals.** It's tempting to `patch("anthropic.resources.messages.Messages.create")`. Don't. That couples your test to a vendor's *private* structure and breaks on every SDK release. Mock at boundaries **you** define: the `LLMProvider` protocol, the repository interface, the HTTP transport (above). If a mock feels awkward, the design is talking to you — the dependency wants to be *injected*."""
))

cells.append(md(
"""## 6 · 🔮 Predict: property-based testing finds the counterexample (§7.3)

`Hypothesis` doesn't take examples — it takes an **invariant** and hunts for an input that breaks it, then *shrinks* it to a minimal failing case. We'll test the chunker.

**Predict before running:** we'll assert two invariants. One is *coverage* — every character of the input appears somewhere in the chunks. The other is *exact reconstruction* — `"".join(chunks) == text`. **Which one does Hypothesis break, and what's the smallest input that breaks it?** Think about what overlap does to the joined string."""
))

cells.append(code(
'''def coverage_holds(text, size, overlap):
    chunks = chunk(text, size=size, overlap=overlap)
    if any(len(c) > size for c in chunks):
        return False
    return set(text) <= set("".join(chunks))      # every char survives — TRUE invariant

def reconstruction_holds(text, size, overlap):
    chunks = chunk(text, size=size, overlap=overlap)
    return "".join(chunks) == text                # FALSE the moment chunks overlap

if HAS_HYPOTHESIS:
    from hypothesis import given, strategies as st, settings

    @settings(max_examples=200, deadline=None)
    @given(st.text(min_size=1), st.integers(min_value=8, max_value=64))
    def test_chunking_covers(text, size):
        overlap = size // 4
        assert coverage_holds(text, size, overlap)
    test_chunking_covers()
    print("coverage invariant: PASSED across generated inputs.")

    # Now watch reconstruction FAIL and shrink to a minimal counterexample.
    @settings(max_examples=500, deadline=None)
    @given(st.text(min_size=1), st.integers(min_value=8, max_value=64))
    def test_chunking_reconstructs(text, size):
        overlap = size // 4
        assert reconstruction_holds(text, size, overlap), (repr(text), size, overlap)
    try:
        test_chunking_reconstructs()
        print("reconstruction: unexpectedly passed (overlap was 0 for all cases).")
    except AssertionError as e:
        print("reconstruction invariant: FAILED, as predicted ->", e)
else:
    # Offline fallback: a deterministic search for a minimal counterexample.
    print("hypothesis not installed — running a tiny deterministic search instead.")
    counter = None
    for text in ["a", "ab", "abcdefghi", "aaaaaaaaa"]:
        if not reconstruction_holds(text, size=8, overlap=2):
            counter = text
            break
    chunks = chunk(counter, size=8, overlap=2)
    print("coverage holds for all tried inputs :", all(
        coverage_holds(t, 8, 2) for t in ["a", "abcdefghi", "aaaaaaaaa"]))
    print("reconstruction breaks on            :", repr(counter))
    print("  chunks       =", chunks)
    print('  "".join len  =', len("".join(chunks)), "vs input len", len(counter),
          "-> overlap double-counts")'''
))

cells.append(md(
"""**What you just saw.** *Coverage* holds for every input Hypothesis can dream up; *reconstruction* fails the instant `overlap > 0`, because the overlap region is double-counted, so `"".join(chunks)` is **longer** than the input. The lesson is sharp: pick an invariant that's *actually true for all inputs*, or the tool will hand you a counterexample on the first run — which is, to be fair, its entire job."""
))

cells.append(md(
"""## 🎯 Senior lens

When the test must touch generated text, assert **properties**, not strings: it *parses as JSON*; the chosen tool is in the registry; the summary is *under the token cap*; the answer *contains the order ID*. Properties survive model upgrades — golden transcripts shatter on them. And keep the two worlds apart: `assert action.tool == "search"` is a unit test and belongs in CI's red/green world; `assert answer_quality > 0.9` is an **eval** (Ch 22) — scored samples on a schedule, not a gate that blocks a merge on a model's mood. Conflating them gives you either a flaky CI or a quality bar that nobody measures."""
))

cells.append(md(
"""## Recap

- The pyramid is a **speed strategy**: push each check to the lowest layer that can catch the defect.
- Split the system: **deterministic shell** (unit tests with a `FakeLLM`) vs **probabilistic core** (evals, Ch 22).
- `FakeLLM` scripts replies and **records prompts**; tests assert **structure** (`action.tool`, `"Oslo" in prompts[0]`), never exact strings.
- A bare `async def` test is **collected but never awaited** without `pytest-asyncio` — green, having run nothing. Mark it or set `asyncio_mode = "auto"`.
- `parametrize` tables the edges; `monkeypatch` scopes env changes with auto-cleanup; `respx` asserts HTTP contracts (retry on 429) with no key.
- Mock **boundaries you own**, not vendor internals like `Messages.create`.
- Property tests assert a *true* invariant — **coverage**, not reconstruction (overlap double-counts)."""
))

cells.append(md(
"""## Exercises

Predict the result before running each.

1. **Record more than prompts.** Extend `FakeLLM` to also record the `kwargs` of each `complete` call (e.g. a `model=` or `max_tokens=`). Write a test asserting the agent passed the budget you expect — *structure*, not the value of the reply.
2. **Make the bug surface.** Take `test_agent_dispatches_search_tool` and script a reply naming an **unregistered** tool. Predict the exception, then assert the agent raises `ValueError` (the deterministic validation path).
3. **Parametrize a real edge.** Add rows to `CASES` for `overlap == size - 1` (max overlap) and a single-character `size == 1`. Predict the chunk count, then confirm `len(c) <= size` still holds.
4. **Flip the invariant.** Change the property test to assert `len("".join(chunks)) == len(text)` and run it. Predict the minimal counterexample Hypothesis (or the fallback) reports, and explain it in one sentence."""
))

cells.append(code('# Exercise 1 — your code here\n'))
cells.append(code('# Exercise 2 — your code here\n'))
cells.append(code('# Exercise 3 — your code here\n'))
cells.append(code('# Exercise 4 — your code here\n'))

cells.append(md(
"""## Next

- ➡️ **Next notebook:** [`07-02-git-and-quality-gates.ipynb`](./07-02-git-and-quality-gates.ipynb) — bisect a regression in O(log n) and assemble the ruff + mypy + pytest gates (pre-commit and CI) that protect `main`.
- 📦 **Template:** the CI workflow these tests run inside lives in [`templates/github-actions-ci/`](../../../templates/github-actions-ci/).
- 🏗️ **Capstone:** this `FakeLLM` fixture and the first agent tests seed the capstone's `tests/`; every later chapter's code — human or generated — enters through the gate built next door.
- 📘 See the book **§7.2–7.3** for the testing pyramid, the `FakeLLM`, and the Hypothesis invariant; model **quality** testing lives in **Ch 22 (evals)**, deliberately *not* in CI."""
))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = os.path.join(DIR, "07-01-pytest-and-testing-nondeterminism.ipynb")
with open(out, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
    f.write("\n")
print("wrote", out)
