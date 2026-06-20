# Blueprint — Ops & Incident-Response Copilot  (solution)

> Appendix G use case · Status: 📋 planned (Phase 1)

## The problem it solves
Triage is slow under pressure and runbook knowledge lives in a few senior heads — the right
responder is asleep, the runbook is out of date, and time-to-resolution suffers. SRE,
platform, and IT ops teams want faster triage, less burnout, and captured institutional
knowledge.

## What it does
A copilot for the people who keep systems running: it triages alerts, correlates signals,
retrieves the relevant runbook, **proposes** (or, when trusted, executes) remediation steps,
and drafts the postmortem afterward. The autonomy dial is tight — default to *propose-not-act*,
with human-in-the-loop as the hard gate on anything that mutates production and dangerous
verbs simply absent from the tool set until earned (Appendix G → "Ops & incident-response
copilot"; Ch 43 autonomous workflow/ops agent).

## Composes (pattern blueprints used)
- [`../agent-loop/`](../agent-loop/) — reasoning to correlate signals + propose remediation (Ch 16).
- [`../rag-pipeline/`](../rag-pipeline/) — retrieval over runbooks, past incidents, and recent changes (Ch 13).
- [`../mcp-server/`](../mcp-server/) — read-mostly, least-privilege tools into observability/logs/deploy systems (Ch 19, 41).
- [`../eval-harness/`](../eval-harness/) — evals + chaos-style testing on historical incidents (Ch 22).
- [`../observability-stack/`](../observability-stack/) — the incident trace that drives postmortem drafting (Ch 23) + append-only audit log (Ch 28).

## Planned structure
```text
incident-response-copilot/
├── README.md
├── PLAN.md
├── app/
│   ├── triage.py             # structured triage output: severity, cause, proposed actions (Ch 15)
│   ├── correlate.py          # agent-loop reasoning over signals (Ch 16)
│   ├── approve.py            # approval gate: agent proposes, engineer approves each mutating step (Ch 20)
│   └── postmortem.py         # draft postmortem from the incident trace (Ch 23)
├── tools/
│   └── ops_mock.py           # read-mostly observability/log/deploy tools via mcp-server
├── audit/
│   └── ledger.py             # append-only audit log of every action (Ch 28)
├── evals/
│   └── incidents_golden.jsonl# historical incidents for triage/chaos testing
├── data/
│   └── runbooks/             # ~4 sample runbooks + past-incident snippets
└── demo.py                   # MOCK: alert → triage + runbook + proposed (gated) remediation
```

## Maps to the book
- **Appendix G:** "Ops & incident-response copilot" (RAG runbooks + scoped tools + HITL; buyer = SRE/platform/IT).
- **Chapters showcased:** 13 (runbook/incident retrieval), 12/41 (scoped least-privilege
  tools), 16 (signal correlation), 20/43 (approval gate, earned autonomy), 15 (structured
  triage), 28 (append-only audit log), 23 (postmortem from trace), 31 (durability over long
  incidents), 22 (evals + chaos testing), 19 (MCP).

## How to adapt it
- Replace `tools/ops_mock.py` with your observability/logging/deploy MCP servers — **read-mostly first**.
- Keep mutating verbs out of the tool set until per-action evals justify autonomy; default propose-not-act.
- Point the rag-pipeline at your runbooks + incident history; add freshness/feedback so guidance isn't stale.
- Wire the audit ledger to your system of record; never let the copilot become a single point of failure.
- Build evals from your historical incidents.

## Phase-2 definition of done
- [ ] `demo.py` runs in MOCK mode; triages an alert, retrieves a runbook, proposes a gated remediation, drafts a postmortem.
- [ ] README frames problem → solution → pitch and links its Appendix-G section + chapters.
- [ ] Mutating actions require approval; audit log is append-only; composes patterns without forking.
- [ ] Eval/chaos set over historical incidents present.
