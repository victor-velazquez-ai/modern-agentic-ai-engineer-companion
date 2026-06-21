# Ops & Incident-Response Copilot — a *solution* blueprint

> A worked example that **composes** five pattern blueprints into one real-world agent.
> Runs free, offline, and deterministically (`COMPANION_MOCK=1`, the default) — no keys, no
> network, no API spend. Maps to **Appendix G → "Ops & incident-response copilot"** and the
> autonomous workflow/ops agent of **Ch 43**.

```bash
python demo.py            # alert -> triage -> runbook -> gated remediation -> postmortem
python evals/run_evals.py # replay historical incidents as a quality + chaos gate
```

---

## The problem

Triage is slow under pressure, and runbook knowledge lives in a few senior heads. The right
responder is asleep, the runbook is out of date, and time-to-resolution suffers. SRE, platform,
and IT-ops teams want **faster triage, less burnout, and captured institutional knowledge** —
without handing an LLM the keys to production.

## The solution

A copilot for the people who keep systems running. Given an alert it:

1. **correlates** read-only signals (metrics, logs, recent deploys),
2. **retrieves** the matching runbook and a similar past incident,
3. **triages** into a structured verdict (severity, suspected cause, proposed actions),
4. **proposes** remediation — and **gates** anything that mutates production behind a human, and
5. **drafts the postmortem** from the recorded trace + audit ledger afterward.

The autonomy dial is tight on purpose: **propose-not-act by default**, human-in-the-loop as the
hard gate on anything that mutates production, and dangerous verbs simply *absent from the agent's
tool set until earned*.

### What it composes (and does **not** fork)

A solution blueprint *uses* pattern blueprints; it never copies their code. Every
`import agent_loop` / `rag_pipeline` / `mcp_server` / `eval_harness` / `observability_stack`
resolves to the one canonical copy two directories up (wired by `app/_bootstrap.py`), so a fix in
a pattern is a fix here, with no second copy to drift.

| Pattern blueprint | Role here | Book |
|---|---|---|
| [`../agent-loop/`](../agent-loop/) | the loop that correlates signals over read-only tools | Ch 16 |
| [`../rag-pipeline/`](../rag-pipeline/) | retrieval over runbooks + past incidents (`app/knowledge.py`) | Ch 13 |
| [`../mcp-server/`](../mcp-server/) | read-mostly, least-privilege ops tools (`tools/ops_mock.py`) | Ch 19, 41 |
| [`../observability-stack/`](../observability-stack/) | the incident trace the postmortem reads from | Ch 23 |
| [`../eval-harness/`](../eval-harness/) | evals + chaos testing on historical incidents (`evals/`) | Ch 22 |

### How the pieces fit

```text
   alert
     │
     ▼
 app/correlate.py ── agent-loop ──► reads metrics/logs/deploys via mcp-server (READ-ONLY)
     │                └─ every read appended to the append-only audit ledger (Ch 28)
     │            ── rag-pipeline ─► retrieves runbook + past incident (app/knowledge.py)
     ▼
 app/triage.py  ──► structured Triage: severity + suspected cause + PROPOSED actions (Ch 15)
     │                         (mutating proposals are labelled + un-run — they carry no authority)
     ▼
 app/approve.py ──► human-in-the-loop gate (Ch 20): the ONLY path a mutating verb can execute,
     │                and only after a human approves THAT action. Default = deny.
     ▼
 app/postmortem.py ─► drafts the postmortem from the trace + the audit ledger (not from memory)
```

The single most important design choice is the **tool split** (`tools/ops_mock.py`):

- **read tools** (`get_metrics`, `search_logs`, `list_deploys`, `service_health`) are
  allow-listed for the agent — the worst a read can do is be wrong, and the loop recovers from a
  wrong read.
- **mutating verbs** (`restart_service`, `rollback_deploy`) are **never** on the agent's
  allow-list. They exist so the copilot can *propose* them; they execute only through the approval
  gate, which builds a *separately scoped* client once a human has signed off. Even a fully
  compromised agent loop cannot reach them.

## Layout

```text
incident-response-copilot/
├── README.md            ← you are here
├── PLAN.md              ← the spec this implements (unchanged)
├── demo.py              ← MOCK end-to-end: alert → triage → gated remediation → postmortem
├── app/
│   ├── _bootstrap.py    ← puts the composed pattern packages on sys.path (no fork)
│   ├── triage.py        ← structured triage output: severity, cause, proposed actions (Ch 15)
│   ├── knowledge.py     ← runbook/incident retrieval over rag-pipeline (Ch 13)
│   ├── correlate.py     ← agent-loop reasoning over read-only signals (Ch 16)
│   ├── approve.py       ← the human-in-the-loop approval gate (Ch 20, 43)
│   └── postmortem.py    ← drafts the postmortem from the trace + ledger (Ch 23)
├── tools/ops_mock.py    ← read-mostly, least-privilege ops tools via mcp-server (Ch 19, 41)
├── audit/ledger.py      ← append-only, hash-chained audit log of every action (Ch 28)
├── evals/
│   ├── incidents_golden.jsonl  ← historical incidents for triage/chaos testing
│   └── run_evals.py            ← scores the real pipeline against the golden set (Ch 22)
└── data/
    ├── runbooks/        ← 4 sample runbooks
    └── past_incidents.md← past-incident snippets (institutional memory)
```

## What the demo shows

Running `python demo.py` triages a `checkout` 5xx storm and prints, in order:

- a structured **SEV1** triage with the suspected cause **grounded in the correlated logs**
  (connection-pool exhaustion) and the retrieved runbook + `INC-204`;
- two **gated** mutating proposals (rollback, restart) — proposed, never auto-run;
- the approval gate run **twice**: first with the safe default (**deny** → nothing executes),
  then with an explicit approval of the deploy-correlated rollback (**approved → executed →
  audited**);
- a **postmortem draft** assembled from the incident trace + the append-only ledger;
- the **audit ledger** verifying intact (hash-chained; append-only), and the **trace tree** with
  a `$0.00` cost roll-up.

## The evals (quality + chaos gate)

`evals/incidents_golden.jsonl` replays real-shaped incidents through the *actual* composed
pipeline and asserts the copilot reaches the right severity, **grounds** its cause in the signals,
and proposes the right remediation **as a gated proposal** — never auto-run. The set deliberately
mixes the easy and the dangerous:

- a deploy-correlated rollback (`must-gate`: must propose, gated),
- a flat-error-rate latency case (`propose-not-act`: must propose **no** mutation),
- a grounding case (the cause must come from logs, not imagination).

`run_evals.py` exits non-zero if the mean score drops below threshold, so it runs in CI as a
regression gate. Every eval case also asserts, per run, that the read-only path **executed
nothing** — the chaos invariant.

## How to adapt it to your domain

1. **Swap the tools.** Replace `tools/ops_mock.py`'s in-memory fixture with your
   Datadog/Grafana/Loki/Kubernetes/Argo MCP servers — **read-mostly first**. The
   `SafeMCPClient` allow-list, validation, and timeout guards carry over unchanged.
2. **Keep mutating verbs out** of the agent's tool set until per-action evals justify autonomy.
   Moving a verb from the gated set to the read set *is* "earned autonomy" — and it should be
   driven by `evals/`, not vibes.
3. **Point the RAG at your knowledge.** Drop your runbooks into `data/runbooks/` and your incident
   history into `data/past_incidents.md` (or repoint `app/knowledge.load_corpus`). Add a freshness
   / feedback signal so guidance does not go stale.
4. **Wire the audit ledger to your system of record.** `audit/ledger.py` is append-only and
   hash-chained; swap `export_jsonl`'s sink for an append-only/WORM store or a SIEM. Never let the
   copilot rewrite its own history — and never let it become a single point of failure.
5. **Build evals from your real incidents.** Each resolved incident is a future golden case; the
   postmortem's follow-ups even remind you to add it.

## Going live (no spend by default)

Everything runs in MOCK mode (`COMPANION_MOCK=1`). To go live:

- inject an `llm-gateway`-backed `ModelPort` into the correlation loop (replace the scripted
  "brain" in `app/correlate.py`) — set `COMPANION_MOCK=0`;
- point `tools/ops_mock.py` at your real MCP servers;
- replace the default-deny approver in `app/approve.py` with a real human gate (a CLI prompt, a
  Slack approval button) or a narrowly scoped auto-approve policy you have earned via evals.

Secrets come from the environment; nothing is hard-coded and nothing spends by default.

## Pitch (who buys this)

SRE, platform, and IT-ops teams: **faster triage, captured runbook knowledge, and a copilot that
proposes but does not act** until you let it. The audit ledger and the postmortem mean every
incident makes the next one faster — and the tight autonomy dial means trust is *earned*, not
assumed.
```text
See Appendix G → "Ops & incident-response copilot" and Ch 43 (autonomous workflow/ops agent).
```
