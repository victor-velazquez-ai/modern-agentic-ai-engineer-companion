"""The tracer: build a nested span tree for one agent run, on stdlib alone.

Tracing is *instrumentation you wrap around other code*. The job of this module is to make
that wrapping cheap and idiomatic:

- a ``Tracer`` owns one run and hands out spans;
- ``with tracer.span(...)`` (and the ``run_span`` / ``model_span`` / ``tool_span`` /
  ``retrieval_span`` helpers) opens a child of whatever span is currently active, so
  nesting follows your call stack automatically;
- ``@traced`` decorates a function so each call becomes a span without touching the body.

Why no OpenTelemetry import here? Three reasons that matter for a teaching blueprint:
1. It must run **free and offline in MOCK mode** with only ``requirements.txt`` + stdlib,
   and ``opentelemetry-sdk`` may not even be installed.
2. The *concepts* — a span tree, parent/child links, attributes, timing, status — are the
   thing to learn; OTel is one serialization of them. ``exporters.py`` bridges to real OTel
   when you want a live backend.
3. A self-contained tree is trivially testable: assert on the structure, not on a global
   provider's side effects.

The current span is tracked with :class:`contextvars.ContextVar`, so nesting is correct
across nested ``with`` blocks, decorated calls, and ``asyncio`` tasks.
"""

from __future__ import annotations

import contextvars
import functools
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterator, TypeVar

from . import attributes as attrs
from .attributes import SpanKind

F = TypeVar("F", bound=Callable[..., Any])

# The span currently being executed, per-context. None when no run is active.
_CURRENT_SPAN: contextvars.ContextVar["Span | None"] = contextvars.ContextVar(
    "observability_current_span", default=None
)


class SpanStatus(str, Enum):
    """Terminal status of a span."""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"

    def __str__(self) -> str:
        return self.value


@dataclass
class Span:
    """One node in the run's trace tree.

    A span has a name, a :class:`SpanKind`, a bag of attributes, a parent link, an ordered
    list of children, timing, and a status. The roll-up in ``cost.py`` and the rendering in
    ``exporters.py`` both walk this structure.
    """

    name: str
    kind: SpanKind
    run_id: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent: "Span | None" = field(default=None, repr=False)
    children: list["Span"] = field(default_factory=list, repr=False)
    attributes: dict[str, Any] = field(default_factory=dict)
    status: SpanStatus = SpanStatus.UNSET
    start_time: float = field(default_factory=time.perf_counter)
    end_time: float | None = None

    # --- mutation helpers -------------------------------------------------------
    def set_attribute(self, key: str, value: Any) -> "Span":
        """Attach one attribute; returns self so calls chain."""
        self.attributes[key] = value
        return self

    def set_attributes(self, values: dict[str, Any]) -> "Span":
        """Attach several attributes at once."""
        self.attributes.update(values)
        return self

    def record_usage(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        provider: str | None = None,
    ) -> "Span":
        """Record model token usage on this span using the canonical keys.

        The matching cost is *not* computed here: pricing is a policy that lives in
        ``cost.py`` and is applied by ``roll_up_cost`` so the table is swappable.
        """
        self.set_attributes(
            attrs.usage_attributes(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                provider=provider,
            )
        )
        return self

    def record_exception(self, exc: BaseException) -> "Span":
        """Mark the span as failed and record exception attributes."""
        self.set_attributes(attrs.error_attributes(exc))
        self.status = SpanStatus.ERROR
        return self

    def end(self) -> "Span":
        """Close the span. Idempotent; promotes UNSET → OK on a clean close."""
        if self.end_time is None:
            self.end_time = time.perf_counter()
        if self.status is SpanStatus.UNSET:
            self.status = SpanStatus.OK
        return self

    # --- read helpers -----------------------------------------------------------
    @property
    def duration_ms(self) -> float:
        """Elapsed wall time in milliseconds (0.0 until ended)."""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000.0

    def iter_tree(self) -> Iterator["Span"]:
        """Depth-first pre-order walk of this span and all descendants."""
        yield self
        for child in self.children:
            yield from child.iter_tree()

    def descendants(self) -> Iterator["Span"]:
        """All spans below this one (not including self)."""
        for child in self.children:
            yield from child.iter_tree()


@dataclass
class Trace:
    """A finished (or in-progress) agent run: its root span and its run id."""

    run_id: str
    root: Span

    def iter_spans(self) -> Iterator[Span]:
        """Every span in the run, root first."""
        return self.root.iter_tree()

    def span_count(self) -> int:
        return sum(1 for _ in self.iter_spans())


class Tracer:
    """Creates spans for a single agent run and tracks the active span.

    Typical use::

        tracer = Tracer()
        with tracer.run("support-agent") as run:
            with tracer.model_span("answer", model="claude-...", ...):
                ...
        ConsoleExporter().export(tracer.trace)

    The tracer is intentionally tiny and dependency-free; a real deployment swaps the
    *exporter*, not this.
    """

    def __init__(self, *, run_id: str | None = None) -> None:
        self.run_id = run_id or uuid.uuid4().hex
        self.root: Span | None = None

    @property
    def trace(self) -> Trace:
        """The finished trace. Raises if no run was started."""
        if self.root is None:
            raise RuntimeError("Tracer has no root span yet; open a run() first.")
        return Trace(run_id=self.run_id, root=self.root)

    @staticmethod
    def current_span() -> Span | None:
        """The span currently executing in this context, if any."""
        return _CURRENT_SPAN.get()

    @contextmanager
    def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.CHAIN,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[Span]:
        """Open a span as a child of the currently active span.

        On a clean exit the span is closed OK; if the body raises, the span records the
        exception, is closed ERROR, and the exception re-propagates (we never swallow it —
        instrumentation must be transparent).
        """
        parent = _CURRENT_SPAN.get()
        span = Span(
            name=name,
            kind=kind,
            run_id=self.run_id,
            parent=parent,
            attributes={attrs.SPAN_KIND: str(kind), attrs.RUN_ID: self.run_id},
        )
        if attributes:
            span.set_attributes(attributes)
        if parent is None:
            # First span of the run becomes the root.
            if self.root is None:
                self.root = span
        else:
            parent.children.append(span)

        token = _CURRENT_SPAN.set(span)
        try:
            yield span
        except BaseException as exc:  # noqa: BLE001 - record then re-raise, never swallow
            span.record_exception(exc)
            raise
        finally:
            span.end()
            _CURRENT_SPAN.reset(token)

    # --- typed convenience wrappers ------------------------------------------------
    def run(
        self, name: str, *, attributes: dict[str, Any] | None = None
    ) -> "Any":
        """Open the root RUN span for the whole agent run."""
        return self.span(name, SpanKind.RUN, attributes=attributes)

    def model_span(
        self,
        name: str,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        provider: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> "Any":
        """Open an LLM span with token usage already recorded."""
        merged = attrs.usage_attributes(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            provider=provider,
        )
        if attributes:
            merged.update(attributes)
        return self.span(name, SpanKind.LLM, attributes=merged)

    def tool_span(
        self,
        tool_name: str,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> "Any":
        """Open a TOOL span for one tool/function call."""
        merged: dict[str, Any] = {attrs.TOOL_NAME: tool_name}
        if attributes:
            merged.update(attributes)
        return self.span(tool_name, SpanKind.TOOL, attributes=merged)

    def retrieval_span(
        self,
        name: str = "retrieval",
        *,
        query: str | None = None,
        k: int | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> "Any":
        """Open a RETRIEVAL span for one vector-search / lookup step."""
        merged: dict[str, Any] = {}
        if query is not None:
            merged[attrs.RETRIEVAL_QUERY] = query
        if k is not None:
            merged[attrs.RETRIEVAL_K] = int(k)
        if attributes:
            merged.update(attributes)
        return self.span(name, SpanKind.RETRIEVAL, attributes=merged)


# --- module-level convenience -----------------------------------------------------
# A process-wide default tracer, so a notebook cell or a @traced helper can instrument
# without threading a Tracer through every call. A real service usually owns its tracer
# explicitly; this is the ergonomic default.
_DEFAULT_TRACER: Tracer | None = None


def get_tracer() -> Tracer:
    """The process-wide default tracer, created on first use."""
    global _DEFAULT_TRACER
    if _DEFAULT_TRACER is None:
        _DEFAULT_TRACER = Tracer()
    return _DEFAULT_TRACER


def set_tracer(tracer: Tracer) -> Tracer:
    """Install ``tracer`` as the process-wide default (e.g. to start a fresh run)."""
    global _DEFAULT_TRACER
    _DEFAULT_TRACER = tracer
    return tracer


def traced(
    name: str | None = None,
    kind: SpanKind = SpanKind.CHAIN,
    *,
    tracer: Tracer | None = None,
) -> Callable[[F], F]:
    """Decorator: turn each call of a function into a span on the default tracer.

    Example::

        @traced(kind=SpanKind.TOOL)
        def search(query: str) -> list[str]:
            ...

    The span name defaults to the function's qualified name. Use the explicit
    ``tracer.span(...)`` context manager when you need to set per-call attributes
    (tokens, query, k); the decorator is for the common "just wrap this in a span" case.
    """

    def decorate(func: F) -> F:
        span_name = name or getattr(func, "__qualname__", func.__name__)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            active = tracer or get_tracer()
            with active.span(span_name, kind):
                return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorate
