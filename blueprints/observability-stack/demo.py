"""Runnable demo: trace a (mock) agent run, then print the span tree + total cost.

    python demo.py            # MOCK mode (default): no API spend, deterministic, offline
    COMPANION_MOCK=0 python demo.py   # would use a live exporter/keys (not required here)

What it shows: one agent run becomes a readable trace tree — the loop wraps each model
call, tool call, and retrieval in a span; token usage is attached to the model calls; and
``cost.roll_up_cost`` sums the child model-call costs into every ancestor, so the root span
carries the run total. The console exporter renders all of that with zero infrastructure.

The "agent" here is a tiny scripted stand-in (a support agent: plan → retrieve → call a
tool → answer) so the blueprint is self-contained. In a real system you would wrap your
``agent-loop`` / ``rag-pipeline`` / supervisor with these same spans, and read token/cost
numbers from the ``llm-gateway`` metering layer instead of the canned figures below.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Read-it-by-running-it: make src/ importable without an install step.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from observability_stack import (  # noqa: E402
    ConsoleExporter,
    SpanKind,
    Tracer,
    summarize,
)

# Default to MOCK so the demo is free, offline, and deterministic. We never read a key here.
MOCK = os.getenv("COMPANION_MOCK", "1") != "0"


def mock_model_call(prompt: str, *, model: str) -> tuple[str, int, int]:
    """A stand-in for a real model call.

    Returns ``(text, input_tokens, output_tokens)`` with canned, realistic token counts so
    the cost roll-up has something to add up — and so the run prices identically every time.
    A live implementation would call the ``llm-gateway`` and read usage off the response.
    """
    input_tokens = 40 + len(prompt) // 4  # rough, deterministic token estimate
    output_tokens = 120
    text = f"[mock:{model}] response to: {prompt[:48]}"
    return text, input_tokens, output_tokens


def run_mock_agent(tracer: Tracer) -> str:
    """Scripted support-agent run, fully instrumented with spans."""
    with tracer.run("support-agent", attributes={"agent.session.id": "sess-42"}):
        question = "How do I get a refund for an order placed last week?"

        # 1) Plan the answer with a model call.
        with tracer.model_span(
            "plan",
            model="claude-sonnet-4",
            input_tokens=0,  # patched below from the mock call
            output_tokens=0,
            attributes={"step": "plan"},
        ) as plan_span:
            _, itok, otok = mock_model_call(question, model="claude-sonnet-4")
            plan_span.record_usage(
                model="claude-sonnet-4", input_tokens=itok, output_tokens=otok
            )

        # 2) Retrieve supporting docs (a retrieval span; no model cost of its own).
        with tracer.tool_span("knowledge_base"):
            with tracer.retrieval_span(query=question, k=4) as ret:
                hits = ["refunds.md#policy", "orders.md#window", "faq.md#refunds"]
                ret.set_attribute("agent.retrieval.hits", len(hits))

        # 3) Call an external tool (deterministic; no model cost).
        with tracer.tool_span("lookup_order", attributes={"order_id": "A-1007"}) as tool:
            tool.set_attribute("order.status", "delivered")

        # 4) Compose the final answer with another (cheaper) model call.
        with tracer.model_span(
            "answer",
            model="claude-haiku-4",
            input_tokens=0,
            output_tokens=0,
            attributes={"step": "answer"},
        ) as answer_span:
            grounded_prompt = question + "\n\nContext:\n" + "\n".join(hits)
            text, itok, otok = mock_model_call(grounded_prompt, model="claude-haiku-4")
            answer_span.record_usage(
                model="claude-haiku-4", input_tokens=itok, output_tokens=otok
            )
        return text


def main() -> int:
    mode = "MOCK (offline, no API spend)" if MOCK else "LIVE"
    print(f"observability-stack demo · mode: {mode}\n")

    tracer = Tracer(run_id="demo-0001")
    answer = run_mock_agent(tracer)

    # The console exporter renders the tree and runs the cost roll-up.
    print("Trace tree")
    print("-" * 60)
    ConsoleExporter(show_tokens=True).export(tracer.trace)

    # A compact cost/token summary on top of the same trace.
    summary = summarize(tracer.trace)
    print("\nCost summary")
    print("-" * 60)
    print(f"  model calls : {summary.llm_call_count}")
    print(f"  tokens      : {summary.input_tokens} in + {summary.output_tokens} out "
          f"= {summary.total_tokens}")
    for model, usd in sorted(summary.per_model_usd.items()):
        print(f"  {model:<20} ${usd:.6f}")
    print(f"  {'TOTAL':<20} ${summary.total_usd:.6f}")

    print(f"\nFinal answer: {answer}")
    print(
        "\nNext: wrap your own agent-loop / rag-pipeline with these spans, and feed token "
        "usage from the llm-gateway metering layer. See README.md."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
