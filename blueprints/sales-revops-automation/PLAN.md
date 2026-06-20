# Blueprint — Sales & RevOps Automation  (solution)

> Appendix G use case · Status: 📋 planned (Phase 1)

## The problem it solves
Reps lose selling time to data entry and research, and the CRM — the system the whole
forecast depends on — is perpetually incomplete and out of date. Sales leaders and RevOps
want reclaimed selling time, a cleaner pipeline, and faster, more personalized follow-up.

## What it does
A set of agents that remove the busywork around the revenue motion: enriching CRM records,
turning call recordings and meeting notes into structured CRM updates, drafting personalized
outreach and follow-ups, and surfacing next-best actions. It runs as a **workflow** more than
a chat window, and **drafts go to a human to send** — outbound under an agent's name
unsupervised is a brand risk (Appendix G → "Sales & RevOps automation"; Ch 43 autonomous
workflow agent).

## Composes (pattern blueprints used)
- [`../agent-loop/`](../agent-loop/) — tool use + summarization over a workflow (Ch 12).
- [`../rag-pipeline/`](../rag-pipeline/) — retrieval over past winning messaging and account history for grounded drafting (Ch 13).
- [`../mcp-server/`](../mcp-server/) — clean tool boundary to CRM and call/meeting tooling (Ch 19).
- [`../eval-harness/`](../eval-harness/) — evals on extraction accuracy + guardrails against sending to the wrong contact (Ch 22, 41).
- [`../observability-stack/`](../observability-stack/) — trace nightly hygiene/enrichment jobs.

## Planned structure
```text
sales-revops-automation/
├── README.md
├── PLAN.md
├── workflow/
│   ├── call_to_crm.py        # structured extraction of outcomes/next steps → fields (Ch 15)
│   ├── enrich.py             # external-data enrichment tool calls (mock)
│   ├── draft_outreach.py     # rag-pipeline-grounded follow-up drafting → human to send (Ch 20)
│   └── schedules.py          # background jobs: nightly hygiene + enrichment (Ch 31)
├── tools/
│   └── crm_mock.py           # mock CRM via mcp-server (conservative writes only)
├── evals/
│   └── extraction_golden.jsonl
├── data/
│   └── calls/                # ~3 sample call transcripts + account snapshots
└── demo.py                   # MOCK: transcript → CRM update + drafted (unsent) outreach
```

## Maps to the book
- **Appendix G:** "Sales & RevOps automation" (tool use + summarization; buyer = Sales/RevOps).
- **Chapters showcased:** 12 (tool use/summarization), 15 (structured field extraction), 13
  (playbook/account retrieval), 19 (CRM/meeting tooling via MCP), 20 (human-on-send gate), 31
  (background jobs/schedules), 22/41 (extraction evals + wrong-recipient guardrails).

## How to adapt it
- Replace `tools/crm_mock.py` with your CRM's MCP/API and your call/meeting source.
- **Keep a human on send** until trust is earned; outbound under the agent's name is brand risk.
- Write CRM fields **conservatively and flag uncertainty** — bad data in the forecast is worse than missing data.
- Tune `enrich.py` to your enrichment providers; schedule nightly hygiene to your cadence.
- Build extraction evals from your real call outcomes.

## Phase-2 definition of done
- [ ] `demo.py` runs in MOCK mode; produces a CRM update and a *drafted, unsent* outreach email.
- [ ] README frames problem → solution → pitch and links its Appendix-G section + chapters.
- [ ] Low-confidence fields are flagged (conservative writes); wrong-recipient guardrail present; composes patterns without forking.
- [ ] Extraction-accuracy eval set present.
