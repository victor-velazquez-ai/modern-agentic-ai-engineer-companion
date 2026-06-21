# Talk-to-Your-Data Analytics Copilot — a **solution** blueprint

> **Appendix G #5** · A text-to-SQL copilot over a data warehouse. Buyer: **Data / RevOps / execs**.
> Runs **free and offline** in MOCK mode (the default) — no API spend, secrets from env.

This is a **solution** blueprint: it doesn't invent new mechanisms, it **composes the pattern
blueprints** ([`../agent-loop/`](../agent-loop/), [`../rag-pipeline/`](../rag-pipeline/),
[`../eval-harness/`](../eval-harness/), [`../observability-stack/`](../observability-stack/)) into a
job a company pays for. It **composes them by relative import — it never forks them** (see
[`app/_compose.py`](app/_compose.py)).

---

## The problem → the solution

**The problem (the BI bottleneck).** Every *"what were signups by region last quarter?"* becomes a
ticket to a scarce analyst, so decisions wait in a queue and anyone who can't write SQL is locked
out of their own data. Teams want a *cycle-time collapse* — from days to seconds — for routine
questions.

**The solution (a copilot, not an oracle).** Ask in plain language; get the answer, **and the SQL
behind it**. Under the hood it does structured text-to-SQL against a *known* schema, grounded by
retrieval over table/column docs and a semantic layer, with a **verification check that runs before
the query does**, and execution that is **read-only, row-limited, and timeout-guarded**. Because a
*plausible-looking wrong number is worse than no answer*, the human always sees the SQL and can
correct it, and a golden eval set guards the numbers.

```
   "revenue by region last quarter?"
                │
   rag-pipeline │  retrieve the RIGHT tables/joins/metrics from the semantic layer   (Ch 13)
                ▼
   generate     │  NL → structured, schema-valid SqlPlan (metric expansion)          (Ch 15)
                ▼
   verify       │  read-only? schema-grounded? bounded?  —— BEFORE it runs           (Ch 16)
                ▼
   agent-loop   │  run the verified SQL as the loop's single read-only tool          (Ch 12, 41)
                ▼
   observability│  every stage traced: SQL, row counts, cost                          (Ch 23)
                ▼
   answer  +  "show me the SQL"                                                        (Ch 20)
```

---

## Quickstart (MOCK — free, offline, deterministic)

```bash
python data/build_warehouse.py   # build the bundled mock warehouse (data/warehouse.sqlite)
python demo.py                   # walk a few questions; print answer + SQL + trace
python demo.py "revenue by region"   # ask one ad-hoc question
python evals/run_evals.py        # grade question → expected rows (exits non-zero on a wrong number)
```

`COMPANION_MOCK=1` (the default) keeps everything offline: the planner is a deterministic mock and
no LLM is called. Setting `COMPANION_MOCK=0` opts into the live path (see **Live path** below) and
fails loudly until you wire an `llm-gateway` client — it never spends tokens behind your back.

---

## What's inside

```text
text-to-sql-analytics/
├── README.md                  # this file
├── PLAN.md                    # the spec (unchanged)
├── demo.py                    # MOCK: NL question → verified SQL → result + "show me the SQL" + trace
├── app/
│   ├── _compose.py            # puts the 4 pattern blueprints on sys.path (compose, don't fork)
│   ├── semantic.py            # loads semantic/metrics.yaml into typed objects (the make-or-break asset)
│   ├── nl_to_sql.py           # NL → SqlPlan, grounded via rag-pipeline retrieval        (Ch 13, 15)
│   ├── verify.py              # read-only / schema / bounded checks before execution     (Ch 16, 41)
│   ├── run.py                 # read-only, row-limited, timeout-guarded execution        (Ch 12, 40, 41)
│   └── pipeline.py            # COMPOSES all four patterns into one CopilotAnswer        (Ch 16, 23)
├── semantic/
│   └── metrics.yaml           # the semantic layer / metric definitions (invest here)
├── evals/
│   ├── questions_golden.jsonl # question → expected result rows (+ must-block safety cases)
│   └── run_evals.py           # COMPOSES eval-harness; result-set grader; CI gate        (Ch 22)
└── data/
    ├── build_warehouse.py     # deterministically (re)builds the mock warehouse
    └── warehouse.sqlite       # tiny read-only mock warehouse (generated)
```

### How each pattern is composed (not forked)

| Pattern blueprint | Composed where | What it contributes |
|---|---|---|
| [`rag-pipeline`](../rag-pipeline/) | `app/nl_to_sql.py` (`SemanticIndex`) | Hybrid retrieval + rerank over the semantic layer's schema/metric docs, so language maps to the **right** tables/joins/metrics instead of dumping the whole schema into a prompt. |
| [`agent-loop`](../agent-loop/) | `app/pipeline.py` (`_execute_via_agent_loop`) | The verified query is the loop's single `run_sql` tool; execution inherits the loop's turn cap, malformed-call repair, and failure isolation. Verification runs **before** the tool is offered. |
| [`observability-stack`](../observability-stack/) | `app/pipeline.py` (`ask`) | Each stage (`generate` / `verify` / `execute` / `run_sql`) is a span carrying the SQL, row counts, and (mock) token cost; the run renders as a trace tree with a cost roll-up. |
| [`eval-harness`](../eval-harness/) | `evals/run_evals.py` | Golden set + a domain `ResultMatch` grader (result-set equality, and "this must be blocked"), aggregated into a report with a non-zero CI exit on any wrong number. |

---

## The make-or-break asset: the semantic layer

A text-to-SQL copilot is only as good as the contract between business language and the physical
schema. That contract is [`semantic/metrics.yaml`](semantic/metrics.yaml), and **most of the
adaptation work lives there**, not in the prompt:

- **Schema** — every table and column documented in plain English. This is the text the
  rag-pipeline retrieves over, so a question's words find the right grain.
- **Metrics** — each business metric pinned to **one canonical SQL expression**. `revenue` is not
  `SUM(amount_usd)`; it is `SUM(amount_usd) WHERE status='completed'`. Pinning it here is what keeps
  every revenue answer refund-correct and consistent.
- **Dimensions & joins** — the "by region / by month" slices and the canonical join path, spelled
  out so the copilot resolves grain instead of guessing.

---

## How to adapt it to **your** domain

1. **Rewrite `semantic/metrics.yaml`** for your warehouse: your tables, plain-English column docs,
   your canonical metric SQL, your dimensions and join paths. This is 80% of the work — invest here.
2. **Point `app/run.py` at your warehouse.** Replace `connect_readonly` with your engine's
   connection, created from **read-only, row-limited, timeout-guarded** credentials. (Don't rely on
   the verifier alone — defense in depth: the DB account itself should be read-only.)
3. **Load your real schema/column docs into the rag-pipeline** (via `schema_docs()`), so joins
   resolve to the right grain on questions you didn't anticipate.
4. **Build evals on real questions** in `evals/questions_golden.jsonl`. Grade the **result set**,
   not the prose — a confidently wrong number erodes trust faster than an outage. Add a case the day
   you find a bug.
5. **Keep the cost guards.** The `LIMIT` requirement and the timeout are what stop a careless
   question from scanning a petabyte; tune them to your warehouse's billing model.
6. **Keep "show me the SQL".** Treat it as a copilot — surface the query so a human can read, trust,
   or correct it. Don't ship it as an oracle.

---

## Live path (opt-in, costs money)

The mock planner in `app/nl_to_sql.py` (`SqlGenerator._live_plan`) and the model seam in the
agent-loop are where a real LLM drops in:

- Set `COMPANION_MOCK=0` and inject an [`llm-gateway`](../llm-gateway/) client that returns the same
  `SqlPlan` shape, prompted with `self.index.retrieve(question)` as the grounded context.
- Provide credentials via **environment variables** (e.g. `ANTHROPIC_API_KEY`, warehouse DSN); no
  secret is read from anything but the environment, and nothing spends tokens unless you opt in.
- Verification, execution, tracing, and the evals are **unchanged** on the live path — only the
  generator's planner is swapped. That's the payoff of composing patterns behind stable seams.

---

## Maps to the book

- **Appendix G #5** — "Talk-to-your-data analytics copilot" (text-to-SQL over a warehouse).
- **Chapters showcased:** 15 (structured SQL generation), 13 (schema + semantic-layer retrieval),
  16 (query verification / the reasoning check), 12 (read-only execution tool), 20 ("show me the
  SQL" affordance), 23 (tracing + cost), 40/41 (cost guards, read-only creds, row limits),
  22 (question → answer evals).
