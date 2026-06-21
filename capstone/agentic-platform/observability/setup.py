"""Observability setup — choose and wire an exporter from the environment (Ch 23).

The platform never hard-codes *where traces go*; that is a deploy-time decision read from the
environment (twelve-factor, Ch 28). This module is the one place that turns config into a live
exporter, so the rest of the code instruments against :mod:`observability.tracing` and stays
oblivious to the backend.

Configuration (env only — endpoints/keys never live in code):

* ``COMPANION_MOCK`` — when ``"1"`` (the repo default) force the offline **console** exporter,
  so nothing leaves the process and no collector is required. This is what CI and any reader
  without a backend get for free.
* ``OBSERVABILITY_EXPORTER`` — explicit exporter name (``console`` | ``json`` | ``otlp`` |
  ``phoenix`` | ``langfuse``). Overrides the inference below.
* ``OTEL_EXPORTER_OTLP_ENDPOINT`` — where OTLP traces go. If set (and not in MOCK), the
  default exporter becomes ``otlp`` pointed at that endpoint.

Nothing here imports OpenTelemetry: the OTel-backed exporters import their heavy deps lazily
inside ``export`` (see ``exporters.py``), so importing this module is always cheap and safe.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .exporters import Exporter, get_exporter
from .tracing import Tracer, set_tracer

MOCK_ENV = "COMPANION_MOCK"
EXPORTER_ENV = "OBSERVABILITY_EXPORTER"
OTLP_ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_ENDPOINT"


def _is_mock() -> bool:
    """True when the platform must stay offline (the repo-wide default)."""

    return os.getenv(MOCK_ENV, "1") == "1"


@dataclass(frozen=True)
class ObservabilityConfig:
    """The resolved observability wiring for this process."""

    exporter_name: str
    endpoint: str | None
    mock: bool


def resolve_config() -> ObservabilityConfig:
    """Read the environment and decide which exporter to use (without constructing it).

    Resolution order: MOCK forces ``console``; otherwise an explicit
    ``OBSERVABILITY_EXPORTER`` wins; otherwise an ``OTEL_EXPORTER_OTLP_ENDPOINT`` implies
    ``otlp``; otherwise the offline ``console`` exporter.
    """

    mock = _is_mock()
    endpoint = os.getenv(OTLP_ENDPOINT_ENV) or None

    if mock:
        name = "console"
    elif os.getenv(EXPORTER_ENV):
        name = os.environ[EXPORTER_ENV].strip().lower()
    elif endpoint:
        name = "otlp"
    else:
        name = "console"

    return ObservabilityConfig(exporter_name=name, endpoint=endpoint, mock=mock)


def exporter_from_env() -> Exporter:
    """Construct the exporter implied by the environment.

    With no configuration at all (or ``COMPANION_MOCK=1``) you get the offline, zero-spend
    :class:`~observability.exporters.ConsoleExporter`. Set ``OTEL_EXPORTER_OTLP_ENDPOINT`` (and
    ``COMPANION_MOCK=0``) to ship traces to a real OTLP collector instead.
    """

    cfg = resolve_config()
    if cfg.exporter_name in ("otlp", "phoenix", "langfuse") and cfg.endpoint:
        return get_exporter(cfg.exporter_name, endpoint=cfg.endpoint)
    return get_exporter(cfg.exporter_name)


def configure_observability(*, run_id: str | None = None) -> tuple[Tracer, Exporter]:
    """Install a fresh default tracer and return it alongside the env-selected exporter.

    Call once at process/app startup (e.g. the FastAPI lifespan in ``app/main.py`` or a Celery
    worker bootstrap). Returns ``(tracer, exporter)`` so the caller can open a run on the
    tracer and hand the finished trace to the exporter::

        tracer, exporter = configure_observability()
        with tracer.run("agent-run"):
            ...
        exporter.export(tracer.trace)
    """

    tracer = set_tracer(Tracer(run_id=run_id))
    exporter = exporter_from_env()
    return tracer, exporter
