"""observability_stack — OpenTelemetry-style tracing + cost accounting for agent runs.

Wrap an agent run in spans so it becomes a readable trace tree, attach token usage and
cost to those spans, roll the cost up per run, and export the result (console by default,
OTLP/Phoenix/Langfuse optionally). Built to instrument the other blueprints —
``agent-loop``, ``rag-pipeline``, ``multi-agent-supervisor``, ``llm-gateway`` — without
depending on any of them.

Runs **free and offline in MOCK mode**: the console path and cost roll-up use only stdlib;
the OTel-backed exporters import their (optional) dependencies lazily.

Quick start::

    from observability_stack import Tracer, ConsoleExporter, SpanKind

    tracer = Tracer()
    with tracer.run("support-agent"):
        with tracer.model_span("plan", model="claude-sonnet-4",
                               input_tokens=900, output_tokens=120):
            ...
        with tracer.tool_span("search_docs"):
            ...
    ConsoleExporter().export(tracer.trace)   # prints the tree + total cost

Maps to **Ch 23 — Observability for Agents**; standalone version of the capstone's
``observability/``.
"""

from __future__ import annotations

from .attributes import SpanKind
from .cost import (
    CostSummary,
    ModelPrice,
    PRICES,
    is_known,
    price_for,
    roll_up_cost,
    span_cost,
    summarize,
    token_cost,
    unknown_models,
)
from .exporters import (
    ConsoleExporter,
    Exporter,
    JSONExporter,
    LangfuseExporter,
    OTLPExporter,
    PhoenixExporter,
    get_exporter,
)
from .tracing import (
    Span,
    SpanStatus,
    Trace,
    Tracer,
    get_tracer,
    set_tracer,
    traced,
)

__version__ = "0.1.0"

__all__ = [
    # tracing
    "Tracer",
    "Trace",
    "Span",
    "SpanStatus",
    "SpanKind",
    "traced",
    "get_tracer",
    "set_tracer",
    # cost
    "token_cost",
    "span_cost",
    "roll_up_cost",
    "summarize",
    "CostSummary",
    "price_for",
    "is_known",
    "unknown_models",
    "ModelPrice",
    "PRICES",
    # exporters
    "Exporter",
    "ConsoleExporter",
    "JSONExporter",
    "OTLPExporter",
    "PhoenixExporter",
    "LangfuseExporter",
    "get_exporter",
]
