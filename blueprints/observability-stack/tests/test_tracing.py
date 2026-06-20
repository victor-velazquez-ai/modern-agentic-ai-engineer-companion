"""Tracing: spans nest correctly into a single run tree.

The contract under test is the one the PLAN calls out — "spans nest correctly into a run
tree." We assert structure (parent/child links, depth, ordering), context tracking across
nested ``with`` blocks, status promotion, and that instrumentation is transparent (an
exception inside a span is recorded *and* re-raised, never swallowed).
"""

from __future__ import annotations

import pytest

from observability_stack import Span, SpanKind, SpanStatus, Tracer
from observability_stack.tracing import get_tracer, set_tracer, traced


def test_single_span_becomes_root() -> None:
    tracer = Tracer()
    with tracer.run("agent") as root:
        assert isinstance(root, Span)
    trace = tracer.trace
    assert trace.root is root
    assert root.kind is SpanKind.RUN
    assert root.parent is None
    assert trace.span_count() == 1
    assert root.status is SpanStatus.OK  # clean close promotes UNSET -> OK


def test_children_nest_under_active_span() -> None:
    tracer = Tracer()
    with tracer.run("agent") as root:
        with tracer.model_span(
            "plan", model="claude-sonnet-4", input_tokens=10, output_tokens=5
        ) as model:
            with tracer.tool_span("search") as tool:
                pass
        with tracer.retrieval_span(query="q", k=3) as ret:
            pass

    # plan and retrieval are direct children of the run, in call order.
    assert [c.name for c in root.children] == ["plan", "retrieval"]
    # the tool nests under the model span (it was active when tool_span opened).
    assert model.children == [tool]
    assert tool.parent is model
    assert ret.parent is root
    assert ret.kind is SpanKind.RETRIEVAL
    assert tracer.trace.span_count() == 4


def test_tree_iteration_is_preorder_depth_first() -> None:
    tracer = Tracer()
    with tracer.run("r"):
        with tracer.span("a", SpanKind.CHAIN):
            with tracer.span("a1", SpanKind.CHAIN):
                pass
        with tracer.span("b", SpanKind.CHAIN):
            pass
    names = [s.name for s in tracer.trace.iter_spans()]
    assert names == ["r", "a", "a1", "b"]


def test_current_span_restored_after_each_block() -> None:
    tracer = Tracer()
    assert Tracer.current_span() is None
    with tracer.run("r") as root:
        assert Tracer.current_span() is root
        with tracer.span("child", SpanKind.CHAIN) as child:
            assert Tracer.current_span() is child
        # back to the parent once the child block exits
        assert Tracer.current_span() is root
    assert Tracer.current_span() is None


def test_run_id_is_shared_by_all_spans() -> None:
    tracer = Tracer()
    with tracer.run("r"):
        with tracer.tool_span("t"):
            pass
    ids = {s.run_id for s in tracer.trace.iter_spans()}
    assert ids == {tracer.run_id}


def test_exception_is_recorded_and_reraised() -> None:
    tracer = Tracer()
    with pytest.raises(ValueError, match="boom"):
        with tracer.run("r"):
            with tracer.tool_span("flaky") as tool:
                raise ValueError("boom")

    # The span recorded the failure but the run root still closed.
    assert tool.status is SpanStatus.ERROR
    assert tool.attributes["error"] is True
    assert tool.attributes["error.type"] == "ValueError"
    assert "boom" in tool.attributes["error.message"]
    assert tracer.trace.root.end_time is not None


def test_span_durations_are_recorded() -> None:
    tracer = Tracer()
    with tracer.run("r") as root:
        pass
    assert root.end_time is not None
    assert root.duration_ms >= 0.0


def test_traced_decorator_uses_default_tracer() -> None:
    set_tracer(Tracer())  # fresh default so this test is isolated

    @traced("compute", kind=SpanKind.CHAIN)
    def compute(x: int) -> int:
        return x * 2

    with get_tracer().run("r"):
        assert compute(21) == 42

    names = [s.name for s in get_tracer().trace.iter_spans()]
    assert "compute" in names


def test_record_usage_sets_canonical_attributes() -> None:
    tracer = Tracer()
    with tracer.run("r"):
        with tracer.span("call", SpanKind.LLM) as span:
            span.record_usage(
                model="claude-haiku-4",
                input_tokens=100,
                output_tokens=40,
                provider="anthropic",
            )
    assert span.attributes["gen_ai.request.model"] == "claude-haiku-4"
    assert span.attributes["gen_ai.usage.input_tokens"] == 100
    assert span.attributes["gen_ai.usage.output_tokens"] == 40
    assert span.attributes["gen_ai.usage.total_tokens"] == 140
    assert span.attributes["gen_ai.system"] == "anthropic"


def test_trace_raises_before_a_run_starts() -> None:
    tracer = Tracer()
    with pytest.raises(RuntimeError):
        _ = tracer.trace
