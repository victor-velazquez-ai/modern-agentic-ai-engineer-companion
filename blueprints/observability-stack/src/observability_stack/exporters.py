"""Exporters: turn a finished trace into something you can read or ship.

The default is the **console exporter** — pure stdlib, no collector, no network, no API
spend. It renders the span tree as an indented outline with per-span cost and the run
total, which is exactly what you want while learning or in CI: you *see* what the agent did
and what it cost without standing up infrastructure.

The other exporters target real backends (OTLP collector, Arize Phoenix, Langfuse). They
are **optional adapters**: the heavy ``opentelemetry-*`` / vendor packages are imported
*lazily inside the method*, not at module import. That keeps the whole package importable —
and the console path, the cost roll-up, the tests, and ``demo.py`` all runnable — with only
``requirements.txt`` + stdlib, even when OTel is not installed. Choosing and swapping an
exporter is a config decision; the instrumentation in ``tracing.py`` never changes.

Trade-off to keep in mind (see README): the console exporter is for humans and CI; a real
backend gives you search, retention, and dashboards but adds a dependency and (usually) a
running collector. Sampling lives at the exporter boundary too — export every trace while
learning, sample in production.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, Protocol, TextIO, runtime_checkable

from . import attributes as attrs
from . import cost as cost_mod
from .tracing import Span, SpanStatus, Trace


@runtime_checkable
class Exporter(Protocol):
    """Anything that can emit a finished trace."""

    def export(self, trace: Trace) -> Any:  # pragma: no cover - structural type
        ...


# --- Console exporter (default) ---------------------------------------------------

_GLYPH = {
    attrs.SpanKind.RUN: "run",
    attrs.SpanKind.LLM: "llm",
    attrs.SpanKind.TOOL: "tool",
    attrs.SpanKind.RETRIEVAL: "ret",
    attrs.SpanKind.CHAIN: "chn",
}


class ConsoleExporter:
    """Render a trace as an indented tree with cost, to a text stream.

    Default, dependency-free, deterministic. ``export`` runs the cost roll-up first so the
    rendered numbers and the returned string always agree.

    Args:
        stream: where to write (defaults to ``sys.stdout``).
        color: emit ANSI colors (off by default so CI logs and tests stay clean).
        show_tokens: include token counts on LLM spans.
    """

    def __init__(
        self,
        stream: TextIO | None = None,
        *,
        color: bool = False,
        show_tokens: bool = True,
    ) -> None:
        self.stream = stream if stream is not None else sys.stdout
        self.color = color
        self.show_tokens = show_tokens

    def render(self, trace: Trace) -> str:
        """Return the rendered trace as a string (no I/O)."""
        total = cost_mod.roll_up_cost(trace)
        lines: list[str] = []
        self._render_span(trace.root, prefix="", is_last=True, is_root=True, out=lines)
        lines.append("")
        lines.append(f"run {trace.run_id}  ·  {trace.span_count()} spans  ·  ${total:.6f} total")
        unknown = cost_mod.unknown_models(trace)
        if unknown:
            lines.append(f"  ! unpriced models (cost may be understated): {', '.join(sorted(unknown))}")
        return "\n".join(lines)

    def export(self, trace: Trace) -> str:
        """Render and write the trace; also return the rendered string."""
        text = self.render(trace)
        self.stream.write(text + "\n")
        return text

    def _render_span(
        self,
        span: Span,
        *,
        prefix: str,
        is_last: bool,
        is_root: bool,
        out: list[str],
    ) -> None:
        if is_root:
            connector = ""
            child_prefix = ""
        else:
            connector = "`- " if is_last else "|- "
            child_prefix = prefix + ("   " if is_last else "|  ")

        out.append(prefix + connector + self._label(span))

        for i, child in enumerate(span.children):
            self._render_span(
                child,
                prefix=child_prefix,
                is_last=(i == len(span.children) - 1),
                is_root=False,
                out=out,
            )

    def _label(self, span: Span) -> str:
        kind = _GLYPH.get(span.kind, "spn")
        parts = [f"[{kind}] {span.name}"]
        a = span.attributes
        if self.show_tokens and attrs.has_usage(a):
            parts.append(
                f"{a.get(attrs.MODEL)} "
                f"({a.get(attrs.INPUT_TOKENS)}->{a.get(attrs.OUTPUT_TOKENS)} tok)"
            )
        if attrs.COST in a and a[attrs.COST]:
            parts.append(f"${float(a[attrs.COST]):.6f}")
        elif attrs.COST_ROLLUP in a and a[attrs.COST_ROLLUP] and span.kind is not attrs.SpanKind.LLM:
            parts.append(f"sub ${float(a[attrs.COST_ROLLUP]):.6f}")
        if span.status is SpanStatus.ERROR:
            parts.append(f"ERROR: {a.get(attrs.ERROR_MESSAGE, a.get(attrs.ERROR_TYPE, 'error'))}")
        if span.end_time is not None and span.duration_ms:
            parts.append(f"{span.duration_ms:.1f}ms")
        line = "  ".join(parts)
        if self.color:
            line = _colorize(span, line)
        return line


def _colorize(span: Span, line: str) -> str:  # pragma: no cover - cosmetic
    red, green, dim, reset = "\033[31m", "\033[32m", "\033[2m", "\033[0m"
    if span.status is SpanStatus.ERROR:
        return f"{red}{line}{reset}"
    if span.kind is attrs.SpanKind.LLM:
        return f"{green}{line}{reset}"
    return f"{dim}{line}{reset}"


# --- JSON exporter (stdlib; handy for snapshot tests & piping) --------------------


class JSONExporter:
    """Serialize the trace tree to JSON (stdlib only).

    Useful for snapshot tests, for shipping a trace to a log pipeline, or as the on-the-wire
    shape an OTLP adapter would translate. Deterministic given the tree.
    """

    def __init__(self, stream: TextIO | None = None, *, indent: int | None = 2) -> None:
        self.stream = stream
        self.indent = indent

    def to_dict(self, trace: Trace) -> dict[str, Any]:
        cost_mod.roll_up_cost(trace)
        return {
            "run_id": trace.run_id,
            "total_cost_usd": float(trace.root.attributes.get(attrs.COST_ROLLUP, 0.0)),
            "span_count": trace.span_count(),
            "root": _span_to_dict(trace.root),
        }

    def render(self, trace: Trace) -> str:
        return json.dumps(self.to_dict(trace), indent=self.indent, sort_keys=True)

    def export(self, trace: Trace) -> str:
        text = self.render(trace)
        if self.stream is not None:
            self.stream.write(text + "\n")
        return text


def _span_to_dict(span: Span) -> dict[str, Any]:
    return {
        "name": span.name,
        "kind": str(span.kind),
        "span_id": span.span_id,
        "status": str(span.status),
        "duration_ms": round(span.duration_ms, 4),
        "attributes": dict(span.attributes),
        "children": [_span_to_dict(c) for c in span.children],
    }


# --- Optional OTel-backed exporters (lazy import; never needed for MOCK/console) --


class _LazyOTelExporter:
    """Shared machinery for exporters that bridge to a real OpenTelemetry SDK.

    The OTel imports happen in :meth:`export`, so constructing one of these (or importing
    this module) never requires ``opentelemetry`` to be installed. If it is missing we raise
    a clear, actionable error instead of an ImportError deep in the stack.
    """

    name = "otel"

    def __init__(self, endpoint: str | None = None, **options: Any) -> None:
        self.endpoint = endpoint
        self.options = options

    def _span_processor(self) -> Any:  # pragma: no cover - requires optional dep
        raise NotImplementedError

    def export(self, trace: Trace) -> None:  # pragma: no cover - requires optional dep
        try:
            from opentelemetry import trace as ot_trace  # noqa: PLC0415
            from opentelemetry.sdk.resources import Resource  # noqa: PLC0415
            from opentelemetry.sdk.trace import TracerProvider  # noqa: PLC0415
        except ImportError as exc:  # friendly, actionable
            raise RuntimeError(
                f"The '{self.name}' exporter needs OpenTelemetry installed "
                "(`pip install opentelemetry-sdk opentelemetry-exporter-otlp`). "
                "Use ConsoleExporter (the default) for MOCK / offline runs."
            ) from exc

        cost_mod.roll_up_cost(trace)
        provider = TracerProvider(
            resource=Resource.create({"service.name": "observability-stack"})
        )
        provider.add_span_processor(self._span_processor())
        otel_tracer = provider.get_tracer("observability_stack")

        def emit(span: Span, parent_ctx: Any) -> None:
            with otel_tracer.start_as_current_span(span.name) as otel_span:
                for key, value in span.attributes.items():
                    otel_span.set_attribute(key, _otel_safe(value))
                ctx = ot_trace.set_span_in_context(otel_span)
                for child in span.children:
                    emit(child, ctx)

        emit(trace.root, ot_trace.set_span_in_context(ot_trace.INVALID_SPAN))
        provider.force_flush()
        provider.shutdown()


class OTLPExporter(_LazyOTelExporter):
    """Send the trace to any OTLP collector (Jaeger, Tempo, a vendor's OTLP endpoint)."""

    name = "otlp"

    def _span_processor(self) -> Any:  # pragma: no cover - requires optional dep
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: PLC0415
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # noqa: PLC0415

        kwargs = {"endpoint": self.endpoint} if self.endpoint else {}
        return BatchSpanProcessor(OTLPSpanExporter(**kwargs))


class PhoenixExporter(OTLPExporter):
    """Arize Phoenix speaks OTLP; this is OTLP pointed at Phoenix's collector.

    Defaults to Phoenix's local collector endpoint when none is given.
    """

    name = "phoenix"

    def __init__(self, endpoint: str | None = None, **options: Any) -> None:
        super().__init__(endpoint or "http://localhost:6006/v1/traces", **options)


class LangfuseExporter(OTLPExporter):
    """Langfuse ingests OTLP traces; configure its endpoint + keys via env/options."""

    name = "langfuse"


def _otel_safe(value: Any) -> Any:  # pragma: no cover - requires optional dep
    """Coerce an attribute value to an OTLP-allowed primitive (or its JSON string)."""
    if isinstance(value, (str, bool, int, float)):
        return value
    return json.dumps(value, default=str)


# --- Registry: pick an exporter by name (e.g. from an env var) --------------------

_REGISTRY: dict[str, Callable[..., Exporter]] = {
    "console": ConsoleExporter,
    "json": JSONExporter,
    "otlp": OTLPExporter,
    "phoenix": PhoenixExporter,
    "langfuse": LangfuseExporter,
}


def get_exporter(name: str = "console", **options: Any) -> Exporter:
    """Construct an exporter by name. Defaults to the offline console exporter.

    >>> isinstance(get_exporter(), ConsoleExporter)
    True
    """
    key = name.strip().lower()
    if key not in _REGISTRY:
        raise ValueError(
            f"Unknown exporter {name!r}. Choose one of: {', '.join(sorted(_REGISTRY))}."
        )
    return _REGISTRY[key](**options)
