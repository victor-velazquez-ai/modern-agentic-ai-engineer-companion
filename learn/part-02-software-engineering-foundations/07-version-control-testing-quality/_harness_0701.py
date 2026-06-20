# ===== CELL 1 =====
# --- Setup: imports, env, and the MOCK switch ---------------------------------
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
print(f"hypothesis     : {HAS_HYPOTHESIS}      (property section uses a fallback if False)")

# ===== CELL 2 =====
PYRAMID = [
    ("unit",        "a function/class; ms; no network; a FakeLLM",  "MANY  — exhaustive"),
    ("integration", "your code vs a real Postgres/Redis container",  "FEWER — real boundaries"),
    ("e2e",         "a user flow through the deployed stack",        "FEW   — precious & slow"),
]
for layer, what, how_many in PYRAMID:
    print(f"{layer:<12} {what:<46} {how_many}")

print()
print("Rule: a check belongs at the LOWEST layer that can still catch the defect.")
print("Agent logic (routing/parsing/dispatch) is deterministic -> it lives at the base.")

# ===== CELL 3 =====
class FakeLLM:
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

print("FakeLLM + a tiny deterministic Agent are defined.")

# ===== CELL 4 =====
# In pytest this is:
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
print("PASS — asserted on structure + the recorded prompt, never on a brittle string.")

# ===== CELL 5 =====
import warnings

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
print('     asyncio_mode = "auto"')

# ===== CELL 6 =====
# The fix, shown for real: actually await the coroutine (what pytest-asyncio does).
async def _drive():
    try:
        await test_that_should_fail()
        return "PASS (wrong!)"
    except AssertionError as e:
        return f"FAIL (correct): {e}"

print(asyncio.run(_drive()))
print("Awaited -> the assertion runs -> the bug is caught. THAT is what the plugin buys you.")

# ===== CELL 7 =====
def chunk(text: str, size: int, overlap: int) -> list[str]:
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
print(f"All {len(CASES)} parametrized edge cases pass (each is one pytest row).")

# ===== CELL 8 =====
import contextlib

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
print("monkeypatch's whole value is this guaranteed cleanup.")

# ===== CELL 9 =====
async def call_with_one_retry(client_get, url):
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
    print("(install respx to assert against real httpx traffic.)")

# ===== CELL 10 =====
def coverage_holds(text, size, overlap):
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
          "-> overlap double-counts")

# ===== CELL 11 =====
# Exercise 1 — your code here


# ===== CELL 12 =====
# Exercise 2 — your code here


# ===== CELL 13 =====
# Exercise 3 — your code here


# ===== CELL 14 =====
# Exercise 4 — your code here

