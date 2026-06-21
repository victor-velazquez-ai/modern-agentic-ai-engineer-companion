"""Signal correlation via the ``agent-loop`` pattern (Ch 16) + scoped MCP tools + RAG.

This is the brain of the copilot and the densest composition point. Given an :class:`Alert`, it:

1. opens an **observability** span (``observability-stack``) so the whole correlation becomes one
   subtree of the incident trace that later drives the postmortem;
2. drives the **agent loop** (``agent-loop``) over a set of **read-only ops tools** (the MCP
   ``SafeMCPClient`` from ``tools/ops_mock.py``, exposed via ``as_agent_tools`` — already behind
   the allow-list / validation / timeout guards), so the agent *gathers* metrics, logs, and
   deploys instead of hallucinating them;
3. retrieves the matching **runbook + past incidents** (``rag-pipeline`` via ``app/knowledge``);
4. emits a **structured** :class:`Triage` (Ch 15) whose mutating proposals are *gated*, not run.

Every read the agent performs is written to the **append-only audit ledger** (Ch 28) — the
ledger is the on_event sink wired into the loop, so "the copilot looked at X" is evidence, not a
log line that can be lost.

MOCK posture: the model is a deterministic scripted "brain" (the same technique as
``agent-loop/demo.py``) that picks the right read tools for the alert and then signals it is done.
No tokens are spent. On the live path you inject a gateway-backed ``ModelPort`` and delete the
script — the tools, the loop, the gate, and the audit trail are unchanged.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from . import _bootstrap  # noqa: F401  (wire the composed patterns onto sys.path)

from agent_loop import (  # noqa: E402  (after the path bootstrap)
    AgentLoop,
    MockModel,
    ToolCall,
    ToolRegistry,
    assistant,
)
from agent_loop import tool as agent_tool  # noqa: E402
from observability_stack import SpanKind, Tracer  # noqa: E402

from ..audit.ledger import AuditLedger  # noqa: E402
from .knowledge import Knowledge, RunbookHit  # noqa: E402
from .triage import (  # noqa: E402
    Alert,
    ProposedAction,
    Severity,
    Triage,
    severity_from_metrics,
)


def _make_read_tools(client: Any, ledger: AuditLedger) -> ToolRegistry:
    """Wrap the allow-listed MCP read tools as ``agent_loop`` tools, auditing every call.

    We do not hand the model the raw MCP callables; we wrap each so that *every* invocation
    appends a ``read_tool`` entry to the audit ledger first. The guardrails (allow-list, schema
    validation, timeout) still live in the ``SafeMCPClient`` underneath — this layer only adds the
    audit side-effect the incident record needs.
    """
    registry = ToolRegistry()

    specs = {
        "get_metrics": (
            "Read current metrics for a service.",
            {"type": "object", "properties": {"service": {"type": "string"}}, "required": ["service"]},
        ),
        "search_logs": (
            "Search recent log lines for a service.",
            {
                "type": "object",
                "properties": {"service": {"type": "string"}, "query": {"type": "string"}},
                "required": ["service"],
            },
        ),
        "list_deploys": (
            "List recent deploys for a service.",
            {"type": "object", "properties": {"service": {"type": "string"}}, "required": ["service"]},
        ),
        "service_health": (
            "Summarize a service's health.",
            {"type": "object", "properties": {"service": {"type": "string"}}, "required": ["service"]},
        ),
    }

    def make(name: str, description: str, schema: dict[str, Any]):
        @agent_tool(name, description, schema)
        def _call(**kwargs: Any) -> str:
            ledger.append("copilot", "read_tool", {"tool": name, "args": kwargs})
            result = client.call(name, kwargs)
            return json.dumps(result, sort_keys=True)

        return _call

    for tool_name, (desc, schema) in specs.items():
        if client.is_allowed(tool_name):
            registry.add(make(tool_name, desc, schema))
    return registry


def _correlation_brain(alert: Alert) -> Callable[[list], Any]:
    """A deterministic scripted 'brain' for the loop: gather the right reads, then stop.

    Turn 1 issues the read-tool calls a competent responder would (metrics + logs + deploys for
    the alerting service). Turn 2 reads nothing new and emits a final text turn so the loop
    terminates cleanly. This stands in for an LLM with zero spend; the *loop* and the *tools* are
    real. (Mirrors ``agent_loop.echo_calculator_clock`` in the agent-loop demo.)
    """
    service = alert.service

    def turn_one(_transcript: list) -> Any:
        calls = (
            ToolCall(id="m", name="get_metrics", arguments={"service": service}),
            ToolCall(id="l", name="search_logs", arguments={"service": service, "query": "ERROR"}),
            ToolCall(id="d", name="list_deploys", arguments={"service": service}),
        )
        return assistant(text="Gathering signals for the alerting service.", tool_calls=calls)

    def turn_two(_transcript: list) -> Any:
        return assistant(text="Signals gathered; correlating.")

    # MockModel pops one step per model call; callables receive the transcript.
    return [turn_one, turn_two]


def _gather_signals(alert: Alert, client: Any, ledger: AuditLedger, tracer: Tracer) -> dict[str, Any]:
    """Run the agent loop over the read tools and collect the tool results by tool name."""
    registry = _make_read_tools(client, ledger)

    def on_event(name: str, payload: dict) -> None:
        # Thread loop steps into the active observability span as attributes-bearing children.
        if name == "act":
            with tracer.tool_span("loop.act", attributes={"results": payload.get("results", 0)}):
                pass

    loop = AgentLoop(
        model=MockModel(_correlation_brain(alert)),
        tools=registry,
        max_turns=4,
        on_event=on_event,
    )
    result = loop.run(
        alert.describe(),
        system_prompt=(
            "You are an SRE incident-correlation assistant. Use the read-only tools to gather "
            "metrics, logs, and recent deploys for the alerting service. Do not attempt to change "
            "anything; you only observe and report."
        ),
    )

    # Pull the structured tool results back out of the transcript, keyed by tool name.
    signals: dict[str, Any] = {}
    for msg in result.transcript:
        if msg.role == "tool" and msg.tool_result is not None and msg.tool_result.ok:
            try:
                signals[msg.tool_result.name] = json.loads(msg.text)
            except (json.JSONDecodeError, TypeError):
                signals[msg.tool_result.name] = msg.text
    return signals


def _propose_actions(
    alert: Alert, signals: dict[str, Any], hits: list[RunbookHit]
) -> tuple[ProposedAction, ...]:
    """Turn correlated signals + the top runbook into concrete, *labelled* proposals.

    Read-style proposals (paging, watching a dashboard) are non-mutating. The mutating proposals
    (restart, rollback) are emitted **with** ``mutating=True`` and the scoped tool that would run
    them — so the approval gate, not this function, decides whether they ever execute.
    """
    proposals: list[ProposedAction] = []
    metrics = (signals.get("get_metrics", {}) or {}).get("metrics", {})
    logs = (signals.get("search_logs", {}) or {}).get("matches", [])
    deploys = (signals.get("list_deploys", {}) or {}).get("deploys", [])

    log_blob = " ".join(logs).lower()

    # Non-mutating first response: always page + watch on a hot incident.
    proposals.append(
        ProposedAction(
            description=f"Page the {alert.service} on-call and open an incident channel.",
            mutating=False,
            rationale="Standard first response for a customer-facing degradation.",
        )
    )

    # Cause-specific mutating proposals (gated). Driven by correlated evidence, not guesses.
    recent_deploy = next((d for d in deploys if d.get("current")), None)
    if recent_deploy is not None and ("timeout" in log_blob or "pool" in log_blob):
        prev = next((d for d in deploys if not d.get("current")), None)
        to_version = prev.get("version") if prev else "previous"
        proposals.append(
            ProposedAction(
                description=(
                    f"Roll {alert.service} back from {recent_deploy.get('version')} to {to_version} "
                    "(the most recent deploy correlates with the error onset)."
                ),
                mutating=True,
                tool="rollback_deploy",
                args={"service": alert.service, "to_version": str(to_version)},
                rationale="Recent deploy + connection-pool/timeout errors → likely a regression.",
            )
        )
    if "pool" in log_blob or float(metrics.get("cpu", 0.0)) >= 0.85:
        proposals.append(
            ProposedAction(
                description=f"Restart {alert.service} to clear an exhausted connection pool.",
                mutating=True,
                tool="restart_service",
                args={"service": alert.service},
                rationale="Connection-pool exhaustion in logs / high CPU → a restart may recover.",
            )
        )

    return tuple(proposals)


def correlate(
    alert: Alert,
    *,
    client: Any,
    knowledge: Knowledge,
    ledger: AuditLedger,
    tracer: Tracer | None = None,
) -> Triage:
    """Correlate an alert into a structured :class:`Triage` (gather → retrieve → propose).

    This is the function the demo and the eval harness call. It composes four patterns and leaves
    a complete audit + trace behind. It never mutates production: mutating proposals come back
    *labelled and un-run*, for the approval gate to handle.
    """
    tracer = tracer or Tracer()
    ledger.append("copilot", "triage_start", {"alert": alert.id, "service": alert.service})

    with tracer.run(f"correlate:{alert.id}", attributes={"service": alert.service}):
        # 1) gather signals with the agent loop over scoped read tools
        with tracer.span("gather-signals", SpanKind.CHAIN):
            signals = _gather_signals(alert, client, ledger, tracer)

        # 2) retrieve runbooks + past incidents
        with tracer.retrieval_span("runbook-retrieval", query=alert.describe(), k=4):
            hits = knowledge.search(f"{alert.service} {alert.symptom}", k=4)
        ledger.append("copilot", "retrieve", {"sources": [h.source for h in hits]})

        # 3) severity from the freshest metrics (fall back to the alert's snapshot)
        metrics = (signals.get("get_metrics", {}) or {}).get("metrics", {}) or alert.metrics
        severity = severity_from_metrics(metrics)

        # 4) propose (gated) actions
        proposals = _propose_actions(alert, signals, hits)

    suspected = _suspected_cause(signals, hits)
    triage = Triage(
        alert_id=alert.id,
        service=alert.service,
        severity=severity,
        suspected_cause=suspected,
        proposed_actions=proposals,
        runbook_sources=tuple(h.source for h in hits),
    )
    ledger.append(
        "copilot",
        "propose",
        {
            "severity": severity.value,
            "suspected_cause": suspected,
            "actions": [a.description for a in proposals],
            "mutating": [a.tool for a in triage.mutating_actions],
        },
    )
    return triage


def _suspected_cause(signals: dict[str, Any], hits: list[RunbookHit]) -> str:
    """A short, evidence-grounded cause string from logs + the top runbook hit."""
    logs = (signals.get("search_logs", {}) or {}).get("matches", [])
    if logs:
        first = logs[0]
        # Trim to the human-meaningful head of the log line.
        head = first.split(":", 1)[0] if ":" in first else first
        return f"{head.strip()} (per correlated logs)"
    if hits:
        return f"See runbook {hits[0].source}."
    return "Undetermined from available signals."
