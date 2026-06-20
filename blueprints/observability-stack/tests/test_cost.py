"""Cost: child model-call costs roll up to the root span (the PLAN's tested calculation).

We pin the arithmetic of a single priced call, then prove the roll-up sums descendant
model-call costs into every ancestor — so the root's roll-up equals the run total — and that
non-LLM spans carry their subtree total. We also cover the safety rails: free/unknown models
price at $0 and unknown ids are reported.
"""

from __future__ import annotations

import math

from observability_stack import SpanKind, Tracer
from observability_stack.attributes import COST, COST_ROLLUP
from observability_stack.cost import (
    is_known,
    price_for,
    roll_up_cost,
    summarize,
    token_cost,
    unknown_models,
)


def test_token_cost_matches_price_table() -> None:
    # claude-sonnet-4 = $3 / 1M input, $15 / 1M output (illustrative defaults).
    cost = token_cost("claude-sonnet-4", input_tokens=1_000_000, output_tokens=1_000_000)
    assert math.isclose(cost, 18.0, rel_tol=1e-9)
    # 1k in / 500 out -> 0.001*3 + 0.0005*15 = 0.003 + 0.0075 = 0.0105
    cost2 = token_cost("claude-sonnet-4", 1_000, 500)
    assert math.isclose(cost2, 0.0105, rel_tol=1e-9)


def test_unknown_model_is_free_and_flagged() -> None:
    assert token_cost("totally-made-up-model", 1000, 1000) == 0.0
    assert not is_known("totally-made-up-model")


def test_price_lookup_tolerates_dated_and_prefixed_ids() -> None:
    # snapshot date stripped
    assert price_for("claude-sonnet-4-20250514") == price_for("claude-sonnet-4")
    # provider prefix stripped
    assert price_for("anthropic/claude-haiku-4") == price_for("claude-haiku-4")


def _two_call_run() -> Tracer:
    """A run with two model calls under a tool/chain, for roll-up assertions."""
    tracer = Tracer()
    with tracer.run("agent"):
        with tracer.model_span("plan", model="claude-sonnet-4", input_tokens=1000, output_tokens=500):
            pass
        with tracer.tool_span("research"):
            # a model call nested *inside* a tool span (e.g. a sub-agent)
            with tracer.model_span(
                "summarize", model="claude-haiku-4", input_tokens=2000, output_tokens=1000
            ):
                pass
    return tracer


def test_roll_up_sums_children_into_root() -> None:
    tracer = _two_call_run()
    trace = tracer.trace

    total = roll_up_cost(trace)

    # plan: 1000*3/1e6 + 500*15/1e6 = 0.003 + 0.0075 = 0.0105
    plan_cost = 0.0105
    # summarize (haiku $0.80 in / $4 out): 2000*0.8/1e6 + 1000*4/1e6 = 0.0016 + 0.004 = 0.0056
    summarize_cost = 0.0056
    expected = plan_cost + summarize_cost

    assert math.isclose(total, expected, rel_tol=1e-9)
    # root roll-up equals the returned total
    assert math.isclose(trace.root.attributes[COST_ROLLUP], expected, rel_tol=1e-9)

    # the tool span carries only its subtree (the summarize call), not the sibling plan call
    research = next(s for s in trace.iter_spans() if s.name == "research")
    assert math.isclose(research.attributes[COST_ROLLUP], summarize_cost, rel_tol=1e-9)

    # each LLM span carries its own direct cost
    plan = next(s for s in trace.iter_spans() if s.name == "plan")
    assert math.isclose(plan.attributes[COST], plan_cost, rel_tol=1e-9)


def test_roll_up_is_idempotent() -> None:
    tracer = _two_call_run()
    first = roll_up_cost(tracer.trace)
    second = roll_up_cost(tracer.trace)
    assert math.isclose(first, second, rel_tol=1e-12)


def test_non_llm_spans_get_rollup_but_no_direct_cost() -> None:
    tracer = Tracer()
    with tracer.run("r"):
        with tracer.span("phase", SpanKind.CHAIN):
            with tracer.model_span("call", model="gpt-4o-mini", input_tokens=1000, output_tokens=1000):
                pass
    roll_up_cost(tracer.trace)
    phase = next(s for s in tracer.trace.iter_spans() if s.name == "phase")
    # chain span has a subtree roll-up but no direct per-span cost attribute
    assert COST_ROLLUP in phase.attributes
    assert COST not in phase.attributes


def test_mock_run_costs_zero() -> None:
    tracer = Tracer()
    with tracer.run("r"):
        with tracer.model_span("m", model="mock-model", input_tokens=5000, output_tokens=5000):
            pass
    assert roll_up_cost(tracer.trace) == 0.0


def test_summarize_aggregates_tokens_and_per_model() -> None:
    tracer = _two_call_run()
    summary = summarize(tracer.trace)
    assert summary.llm_call_count == 2
    assert summary.input_tokens == 3000
    assert summary.output_tokens == 1500
    assert summary.total_tokens == 4500
    assert set(summary.per_model_usd) == {"claude-sonnet-4", "claude-haiku-4"}
    assert math.isclose(summary.total_usd, 0.0105 + 0.0056, rel_tol=1e-9)


def test_unknown_models_are_reported_from_the_tree() -> None:
    tracer = Tracer()
    with tracer.run("r"):
        with tracer.model_span("m", model="brand-new-model-x", input_tokens=10, output_tokens=10):
            pass
    assert unknown_models(tracer.trace) == {"brand-new-model-x"}
