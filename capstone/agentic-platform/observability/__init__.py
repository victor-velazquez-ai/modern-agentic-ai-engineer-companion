"""The platform's nervous system (Appendix C · ``observability/``).

Tracing, token/dollar accounting, and the export seam for one agent run — the capstone's
assembled counterpart to the ``observability-stack`` blueprint. One run becomes a tree of
spans (a RUN root with LLM / TOOL / RETRIEVAL / CHAIN children); each model-call span carries
token usage; :mod:`observability.cost` rolls that up into per-span and per-run dollars; an
exporter renders the tree to the console (default), JSON, or a real OTLP/Phoenix/Langfuse
backend.

Layout
------
``attributes.py``  span-attribute conventions (OTel-shaped keys), kept as plain constants.
``tracing.py``     the ``Tracer`` / ``Span`` tree, the ``@traced`` decorator, span helpers.
``cost.py``        token → USD pricing + the per-run cost roll-up and summary.
``exporters.py``   console (default, stdlib) / JSON / lazy OTLP-Phoenix-Langfuse adapters.
``setup.py``       read ``OTEL_EXPORTER_OTLP_ENDPOINT`` etc. from env; pick an exporter.

Zero import-time dependency on OpenTelemetry: the console path, the cost roll-up, and the
tests all run on the stdlib alone (``COMPANION_MOCK=1`` default), and the OTel-backed
exporters import their heavy deps lazily inside ``export``. Endpoints/keys come from the
environment only.
"""

from __future__ import annotations

from . import attributes
from .attributes import SpanKind
from .cost import (
    CostSummary,
    ModelPrice,
    PRICES,
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
    get_exporter,
)
from .setup import configure_observability, exporter_from_env
from .tracing import (
    Span,
    SpanStatus,
    Trace,
    Tracer,
    get_tracer,
    set_tracer,
    traced,
)

__all__ = [
    # attributes
    "attributes",
    "SpanKind",
    # tracing
    "Tracer",
    "Span",
    "Trace",
    "SpanStatus",
    "get_tracer",
    "set_tracer",
    "traced",
    # cost
    "ModelPrice",
    "PRICES",
    "price_for",
    "token_cost",
    "span_cost",
    "roll_up_cost",
    "unknown_models",
    "summarize",
    "CostSummary",
    # exporters + setup
    "Exporter",
    "ConsoleExporter",
    "JSONExporter",
    "get_exporter",
    "exporter_from_env",
    "configure_observability",
]

__version__ = "0.1.0"
