"""The loop's control flow: single-turn, multi-turn, the turn cap, and cancellation."""

from __future__ import annotations

import pytest

from agent_loop import (
    AgentLoop,
    MockModel,
    StopReason,
    ToolCall,
    ToolRegistry,
    assistant,
    run_agent,
    tool,
)


# --- a couple of trivial, deterministic tools the tests reuse --------------------------

@tool(
    "add",
    "Add two integers.",
    {
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
    },
)
def add(a: int, b: int) -> int:
    return a + b


@tool("ping", "Return pong.")
def ping() -> str:
    return "pong"


def registry() -> ToolRegistry:
    return ToolRegistry([add, ping])


# --- single turn -----------------------------------------------------------------------

def test_single_turn_completes_with_text():
    """No tool calls => the model's text is the final answer, stop reason COMPLETED."""
    model = MockModel(answer="hello there")
    result = AgentLoop(model=model).run("hi")

    assert result.ok
    assert result.stop_reason is StopReason.COMPLETED
    assert result.output == "hello there"
    assert result.turns == 1


def test_run_agent_convenience_wrapper():
    result = run_agent("hi", model=MockModel(answer="ok"))
    assert result.output == "ok"
    assert result.stop_reason is StopReason.COMPLETED


# --- multi turn ------------------------------------------------------------------------

def test_multi_turn_tool_then_answer():
    """call a tool, read its result, then answer — the core observe/act/observe cycle."""
    model = MockModel(
        [
            assistant(tool_calls=(ToolCall(id="1", name="add", arguments={"a": 2, "b": 3}),)),
            lambda transcript: assistant(text=f"The sum is {transcript[-1].text}."),
        ]
    )
    result = AgentLoop(model=model, tools=registry()).run("add 2 and 3")

    assert result.ok
    assert result.output == "The sum is 5."
    # one assistant tool turn + one assistant answer turn
    assert result.turns == 2
    # the tool result was threaded back into the transcript
    roles = [m.role for m in result.transcript]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]


def test_parallel_tool_calls_in_one_turn():
    """A single assistant turn may request several tools; all run, results threaded in order."""
    model = MockModel(
        [
            assistant(
                tool_calls=(
                    ToolCall(id="1", name="add", arguments={"a": 1, "b": 1}),
                    ToolCall(id="2", name="ping", arguments={}),
                )
            ),
            lambda t: assistant(text="done"),
        ]
    )
    result = AgentLoop(model=model, tools=registry()).run("do both")

    tool_turns = [m for m in result.transcript if m.role == "tool"]
    assert [t.tool_result.content for t in tool_turns] == ["2", "pong"]
    assert result.ok


# --- the turn cap ----------------------------------------------------------------------

def test_max_turns_guard_stops_a_runaway_loop():
    """A model that keeps calling tools forever must be stopped by the cap."""
    forever = MockModel(
        [assistant(tool_calls=(ToolCall(id="x", name="ping", arguments={}),)) for _ in range(50)]
    )
    result = AgentLoop(model=forever, tools=registry(), max_turns=4).run("loop forever")

    assert result.stop_reason is StopReason.MAX_TURNS
    assert not result.ok
    assert result.turns == 4
    assert result.output == ""  # no final answer was produced


def test_max_turns_must_be_at_least_one():
    with pytest.raises(ValueError):
        AgentLoop(model=MockModel(answer="x"), max_turns=0)


# --- cancellation ----------------------------------------------------------------------

def test_cancel_predicate_stops_before_model_call():
    """An external cancel (deadline, user stop) ends the run without further model spend."""
    model = MockModel([assistant(text="should never be reached")])
    # cancel immediately, before the first decide
    result = AgentLoop(model=model).run("hi", cancel=lambda _t: True)

    assert result.stop_reason is StopReason.CANCELLED
    assert model.calls == 0  # we stopped before asking the model to think


def test_cancel_after_first_turn():
    calls = {"n": 0}

    def cancel(_transcript) -> bool:
        calls["n"] += 1
        return calls["n"] > 1  # allow the first decide, cancel before the second

    model = MockModel(
        [
            assistant(tool_calls=(ToolCall(id="1", name="ping", arguments={}),)),
            assistant(text="unreached"),
        ]
    )
    result = AgentLoop(model=model, tools=registry()).run("go", cancel=cancel)

    assert result.stop_reason is StopReason.CANCELLED
    assert model.calls == 1


# --- defaults / reuse ------------------------------------------------------------------

def test_default_loop_runs_offline_with_no_args(monkeypatch):
    """AgentLoop() with nothing wired uses the mock model and runs free."""
    monkeypatch.setenv("COMPANION_MOCK", "1")
    result = AgentLoop().run("anything")
    assert result.stop_reason is StopReason.COMPLETED


def test_loop_is_reusable_across_tasks():
    loop = AgentLoop(model=MockModel(answer="a"))
    r1 = loop.run("task one")
    # fresh transcript per run; first run didn't leak into the second
    r2 = AgentLoop(model=MockModel(answer="b")).run("task two")
    assert r1.output == "a"
    assert r2.output == "b"
    assert len(r1.transcript) == 3  # system + user + assistant
