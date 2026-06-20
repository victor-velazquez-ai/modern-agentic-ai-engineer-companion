"""Exporters: the console exporter emits a complete, well-formed trace (the PLAN's check).

"Complete" = every span in the tree appears; "well-formed" = nesting is shown by
indentation, costs and the run total render, and errors surface. We also cover the JSON
exporter (a stdlib snapshot path), the registry, and that the OTel-backed exporters import
lazily — so importing this module and running these tests never needs ``opentelemetry``.
"""

from __future__ import annotations

import io
import json

import pytest

from observability_stack import (
    ConsoleExporter,
    JSONExporter,
    SpanKind,
    Tracer,
    get_exporter,
)
from observability_stack.exporters import (
    LangfuseExporter,
    OTLPExporter,
    PhoenixExporter,
)


def _sample_run() -> Tracer:
    tracer = Tracer(run_id="run-demo-0001")
    with tracer.run("support-agent"):
        with tracer.model_span(
            "plan", model="claude-sonnet-4", input_tokens=1200, output_tokens=300
        ):
            pass
        with tracer.tool_span("search_docs"):
            with tracer.retrieval_span(query="refund policy", k=4):
                pass
        with tracer.model_span(
            "answer", model="claude-haiku-4", input_tokens=2000, output_tokens=450
        ):
            pass
    return tracer


def test_console_export_contains_every_span() -> None:
    tracer = _sample_run()
    buf = io.StringIO()
    text = ConsoleExporter(stream=buf).export(tracer.trace)

    for name in ["support-agent", "plan", "search_docs", "retrieval", "answer"]:
        assert name in text
    # writes to the stream and returns the same text
    assert buf.getvalue().strip() == text.strip()


def test_console_export_is_well_formed_tree() -> None:
    tracer = _sample_run()
    text = ConsoleExporter(stream=io.StringIO()).render(tracer.trace)
    lines = text.splitlines()

    # root has no tree connector; children are indented under it
    assert lines[0].startswith("[run] support-agent")
    assert any("|- " in ln or "`- " in ln for ln in lines)
    # the nested retrieval is indented deeper than its parent tool span
    tool_line = next(ln for ln in lines if "search_docs" in ln)
    ret_line = next(ln for ln in lines if "retrieval" in ln)
    assert _indent(ret_line) > _indent(tool_line)


def test_console_export_shows_total_cost() -> None:
    tracer = _sample_run()
    text = ConsoleExporter(stream=io.StringIO()).render(tracer.trace)
    assert "total" in text
    assert "$" in text
    # plan 1200*3/1e6 + 300*15/1e6 = 0.0036 + 0.0045 = 0.0081
    # answer 2000*0.8/1e6 + 450*4/1e6 = 0.0016 + 0.0018 = 0.0034  -> 0.0115 total
    assert "0.011500" in text


def test_console_export_marks_errors() -> None:
    tracer = Tracer()
    with pytest.raises(RuntimeError):
        with tracer.run("r"):
            with tracer.tool_span("explode"):
                raise RuntimeError("kaboom")
    text = ConsoleExporter(stream=io.StringIO()).render(tracer.trace)
    assert "ERROR" in text
    assert "kaboom" in text


def test_console_export_flags_unpriced_models() -> None:
    tracer = Tracer()
    with tracer.run("r"):
        with tracer.model_span("m", model="mystery-model", input_tokens=10, output_tokens=10):
            pass
    text = ConsoleExporter(stream=io.StringIO()).render(tracer.trace)
    assert "unpriced" in text
    assert "mystery-model" in text


def test_json_exporter_round_trips() -> None:
    tracer = _sample_run()
    text = JSONExporter().render(tracer.trace)
    data = json.loads(text)
    assert data["run_id"] == "run-demo-0001"
    assert data["span_count"] == 5
    assert data["root"]["name"] == "support-agent"
    assert data["root"]["children"][0]["name"] == "plan"
    assert data["total_cost_usd"] > 0.0


def test_get_exporter_defaults_to_console() -> None:
    assert isinstance(get_exporter(), ConsoleExporter)
    assert isinstance(get_exporter("json"), JSONExporter)
    assert isinstance(get_exporter("OTLP"), OTLPExporter)  # case-insensitive


def test_get_exporter_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unknown exporter"):
        get_exporter("does-not-exist")


def test_otel_exporters_construct_without_opentelemetry_installed() -> None:
    # Constructing must not import opentelemetry (lazy). This passes whether or not the
    # optional dep is present; the heavy import only happens inside export().
    for cls in (OTLPExporter, PhoenixExporter, LangfuseExporter):
        exporter = cls()
        assert hasattr(exporter, "export")
    # Phoenix supplies a sensible default endpoint.
    assert "6006" in PhoenixExporter().endpoint


def _indent(line: str) -> int:
    # Visual depth = where the "[kind]" label starts. The tree draws connectors with
    # "|" and spaces, so a deeper line has its label pushed further right even though it
    # may not start with a literal space.
    return line.index("[")
