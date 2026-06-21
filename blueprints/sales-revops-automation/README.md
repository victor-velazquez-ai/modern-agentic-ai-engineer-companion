# Sales & RevOps Automation — a SOLUTION blueprint

> **Appendix G** · *Modern Agentic AI Engineer* companion repo.
> A **solution** blueprint: it introduces no new library — it **composes** five *pattern*
> blueprints into a working product. It runs as a **workflow**, not a chat window, and **a human
> sends every outbound email**.

```
call transcript ─► CRM update (conservative) ─► enrich ─► draft outreach (UNSENT) ─► human sends
   call_to_crm        crm_mock                  enrich     draft_outreach              you
   agent-loop + mcp   mcp-server                mcp-server rag-pipeline + agent-loop
   Ch 12/15           Ch 19                     Ch 19      Ch 13/20

                          schedules: nightly enrichment + pipeline hygiene (traced) — Ch 23/31
```

---

## The problem

Reps lose selling time to data entry and research, and the CRM — the system the entire forecast
depends on — is perpetually incomplete and out of date. Sales leaders and RevOps want three things:
**reclaimed selling time**, a **cleaner pipeline**, and **faster, more personalized follow-up**.

The trap is the obvious-but-wrong build: an autonomous agent that "works the pipeline" — writes to
the CRM on its own and emails prospects under the rep's name. That fails the two tests that matter
in revenue: **is the data trustworthy** (bad data in the forecast is worse than missing data), and
**is the brand safe** (one bad auto-sent email to the wrong contact is a confidentiality and brand
incident). This blueprint is built to pass both.

## The solution

A set of workflow stages that remove the busywork around the revenue motion while keeping the human
in the two places that matter — the **write into the forecast** and the **send**:

1. **call → CRM.** A finished call's transcript becomes a *structured, confidence-scored* CRM
   update. Each field carries a confidence; the CRM boundary writes the high-confidence ones and
   **flags the rest for a human** — it never poisons the forecast with a guess. *(`workflow/call_to_crm.py`,
   on the `agent-loop`, writing through the `mcp-server` boundary; Ch 12/15.)*
2. **enrich.** Empty firmographic fields (`industry`, `employees`, …) are filled from an external
   provider through the **same guarded MCP boundary** — and only into **empty** slots, never over a
   human-entered value. *(`workflow/enrich.py`; Ch 19.)*
3. **draft outreach.** A follow-up email is **drafted, not sent**: grounded in the winning-messaging
   playbook via the `rag-pipeline` blueprint (hybrid retrieval + rerank), composed on the
   `agent-loop`, and returned with `status: draft`. A **wrong-recipient guardrail** holds any draft
   addressed to a contact that doesn't belong to the account. *(`workflow/draft_outreach.py`; Ch 13/20.)*
4. **schedules.** Background jobs keep the pipeline clean overnight: `nightly_enrichment` fills gaps,
   and a **read-only** `pipeline_hygiene` scan flags stale/under-filled records for a human — it
   writes nothing. Both are **traced** end-to-end. *(`workflow/schedules.py`, via the
   `observability-stack` blueprint; Ch 23/31.)*

A quality gate (`evals/`) scores extraction accuracy and the wrong-recipient guardrail on every run.

### How it composes (does **not** fork) the pattern blueprints

The integration *is* the wiring in `revops/`, `workflow/`, and `tools/`. `revops/compose.py` puts
each sibling pattern's `src/` on `sys.path` and imports its package directly — a bug fixed in
`agent-loop` is a bug fixed here. Nothing is vendored or copied.

| Pattern blueprint        | Role in this solution                                                | Chapter |
|--------------------------|----------------------------------------------------------------------|---------|
| [`agent-loop`](../agent-loop/)                 | The tool-using loop the extraction and drafting run on              | 12/15   |
| [`mcp-server`](../mcp-server/)                 | The guarded, allow-listed boundary to the (mock) CRM + enrichment   | 19      |
| [`rag-pipeline`](../rag-pipeline/)             | Hybrid retrieval over past winning messaging → grounds every draft  | 13      |
| [`eval-harness`](../eval-harness/)             | Extraction-accuracy golden set + wrong-recipient guardrail check    | 22/41   |
| [`observability-stack`](../observability-stack/) | Traces the nightly hygiene / enrichment jobs                       | 23      |

## Run it (MOCK by default — offline, deterministic, **$0**)

```bash
cd blueprints/sales-revops-automation
python demo.py                    # COMPANION_MOCK=1 by default: no keys, no API spend
python -m evals.harness           # extraction-accuracy + wrong-recipient guardrail report
COMPANION_MOCK=0 python demo.py   # live path IF the pattern blueprints are wired to a keyed gateway
```

No module imports an SDK or spends a token in the default mode. Secrets, if any, come from the
environment — never hard-coded. The demo walks two calls and the nightly jobs; you should see:

- **Globex** (`Proposal`): amount, next step, and stage all stated with confidence → **all written**.
- **Acme** (`Discovery`): the buyer named ~$50k but **hedged on finance sign-off** → the amount is
  low-confidence and is **FLAGGED, not written**; only the buy-vs-build stage signal lands. *(This is
  the conservative-write thesis in one screen.)*
- A **drafted, `status: draft`** follow-up for Globex, grounded in cited playbook sources.
- The wrong-recipient guardrail **HOLDING** a draft addressed to `buyer@competitor.com`.
- A **traced** nightly enrichment run and a read-only hygiene scan.

## What's in here

```text
sales-revops-automation/
├── README.md                     # you are here
├── PLAN.md                       # the spec (unchanged)
├── demo.py                       # MOCK: transcript → CRM update + drafted (unsent) outreach
├── revops/
│   ├── __init__.py               # package marker + the design stance
│   └── compose.py                # the composition seam (pattern blueprints onto sys.path; no fork)
├── workflow/
│   ├── call_to_crm.py            # transcript → confidence-scored fields → conservative write (Ch 12/15)
│   ├── enrich.py                 # external-data enrichment via the guarded MCP client     (Ch 19)
│   ├── draft_outreach.py         # rag-grounded follow-up → human-on-send + recipient guard (Ch 13/20)
│   └── schedules.py              # nightly enrichment + read-only hygiene, traced           (Ch 23/31)
├── tools/
│   └── crm_mock.py               # mock CRM exposed over MCP (conservative writes only)      (Ch 19)
├── evals/
│   ├── extraction_golden.jsonl   # extraction-accuracy golden set, eval-harness-loadable     (Ch 22)
│   └── harness.py                # candidate + FieldsMatch grader + the guardrail eval
└── data/
    ├── accounts.json             # 3 seed CRM accounts (some intentionally incomplete)
    ├── enrichment.json           # mock firmographic provider table
    ├── playbook.md               # winning-messaging corpus (the RAG grounding for drafts)
    └── calls/                    # 3 sample call transcripts (discovery / proposal)
```

## How to adapt it to your domain

This blueprint is a *recipe to copy and edit*, not a product to deploy. To point it at your work:

1. **Wire your CRM and call source.** Replace `tools/crm_mock.py` with your CRM's MCP server (or API
   behind an MCP adapter) and your call/meeting source (Gong, Zoom, Fireflies). Keep the
   `SafeMCPClient` allow-list + schema validation — the agent should reach the CRM only through a
   guarded boundary, never a raw SDK call.
2. **Keep a human on send.** `draft_outreach.py` returns a `DraftEmail` with `status: draft` and has
   **no `send()` method** on purpose. Outbound under an agent's name unsupervised is brand risk; keep
   the human-on-send gate until trust is earned, and keep the wrong-recipient guardrail (extend
   `recipient_is_valid` with your contacts list and block external/personal domains for confidential
   content).
3. **Write CRM fields conservatively and flag uncertainty.** Tune `min_confidence` and the detectors
   in `call_to_crm.py` to your data. The rule is universal: **a flagged field a human confirms beats a
   wrong field in the forecast.**
4. **Tune enrichment to your providers.** Point `enrich.py` at your enrichment API and schedule
   `nightly_enrichment` to your cadence. Enrichment fills **empty** slots only — never overwrite a
   human value with a provider guess.
5. **Build extraction evals from your real call outcomes.** Extend `evals/extraction_golden.jsonl`
   with your own transcripts and the fields that *should* end up in the CRM (including the ones that
   should be **withheld**). Gate releases on it with the [`eval-harness`](../eval-harness/) blueprint.
6. **Go live deliberately.** Set `COMPANION_MOCK=0` and inject a gateway-backed model port (for the
   extraction/drafting brains) and embedder (for the playbook index). The loops, tools, the
   conservative-write policy, the guardrail, and the human-on-send gate are **unchanged** — only the
   model behind each seam changes.

## The non-negotiables (Phase-2 definition of done)

- **Conservative writes.** A low-confidence or empty field is **flagged, never written** — bad data
  in the forecast is worse than missing data. (See Acme's held amount in the demo.)
- **A human sends.** The workflow only ever produces a **drafted, unsent** email; there is no send
  path in this code. A **wrong-recipient guardrail** holds any draft addressed outside the account.
- **Composes, never forks.** Five pattern blueprints are imported via `revops/compose.py`; the
  "integration" is the glue, not a copy.
- **Evals present.** An extraction-accuracy golden set plus the recipient-guardrail check gate the
  workflow (`python -m evals.harness`).

---

*Maps to the book — Appendix G: "Sales & RevOps automation" (tool use + summarization; buyer =
Sales/RevOps). Chapters showcased: 12 (tool use/summarization), 15 (structured field extraction), 13
(playbook/account retrieval), 19 (CRM/meeting tooling via MCP), 20 (human-on-send gate), 31
(background jobs/schedules), 22/41 (extraction evals + wrong-recipient guardrails), 23 (observability).*

> The sample accounts, calls, enrichment table, and playbook are **synthetic teaching artifacts.**
