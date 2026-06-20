# Blueprint — Talk-to-Your-Data Analytics Copilot  (solution)

> Appendix G use case · Status: 📋 planned (Phase 1)

## The problem it solves
The BI bottleneck: every "what were signups by region last quarter?" becomes a ticket to a
scarce analyst, so decisions wait on a queue. Data teams, execs, and RevOps want self-serve
analytics — a *cycle-time collapse* from days to seconds for routine questions, plus data
access for people who could never write SQL.

## What it does
A copilot that lets non-technical people ask questions of a data warehouse in plain language
and get answers, charts, and **the SQL behind them**. It does structured text-to-SQL against
a known schema, grounded by retrieval over table/column docs and a semantic layer, with a
verification loop that checks the query before it runs read-only. Treated as a copilot — the
human sees and can correct the SQL — not an oracle (Appendix G → "Talk-to-your-data analytics
copilot").

## Composes (pattern blueprints used)
- [`../agent-loop/`](../agent-loop/) — generate → verify → execute (read-only) → render loop, with a reasoning check before run (Ch 16).
- [`../rag-pipeline/`](../rag-pipeline/) — schema/column documentation + semantic-layer retrieval so language maps to the *right* tables/joins (Ch 13).
- [`../eval-harness/`](../eval-harness/) — question→correct-answer set, because a plausible-looking wrong number is worse than no answer (Ch 22).
- [`../observability-stack/`](../observability-stack/) — trace generated SQL, query cost, and failures.

## Planned structure
```text
text-to-sql-analytics/
├── README.md
├── PLAN.md
├── app/
│   ├── nl_to_sql.py          # structured SQL generation validated vs schema (Ch 15)
│   ├── verify.py             # query verification before execution (Ch 16)
│   └── run.py                # read-only, row-limited, timeout-guarded execution (Ch 12, 41)
├── semantic/
│   └── metrics.yaml          # semantic layer / metric definitions (the make-or-break asset)
├── evals/
│   └── questions_golden.jsonl# question → expected result rows
├── data/
│   └── warehouse.sqlite      # tiny mock warehouse (read-only) for MOCK-mode demo
└── demo.py                   # MOCK: NL question → verified SQL → result + "show me the SQL"
```

## Maps to the book
- **Appendix G:** "Talk-to-your-data analytics copilot" (text-to-SQL over a warehouse; buyer = Data/RevOps/execs).
- **Chapters showcased:** 15 (structured SQL generation), 13 (schema + semantic-layer
  retrieval), 16 (query verification), 12 (read-only execution tool), 38 (charts/result
  rendering), 20 ("show me the SQL" affordance), 40/41 (cost guards, read-only creds, row
  limits), 22 (question→answer evals).

## How to adapt it
- Point `app/run.py` at your warehouse with **read-only, row-limited, timeout-guarded** credentials.
- Invest in `semantic/metrics.yaml` — the semantic layer is the make-or-break, not the prompt.
- Load your table/column docs into the rag-pipeline so joins resolve to the right grain.
- Build evals on real questions; a confidently wrong number erodes trust faster than an outage.
- Add cost guards so a careless question cannot scan a petabyte.

## Phase-2 definition of done
- [ ] `demo.py` runs in MOCK mode against the bundled SQLite warehouse; surfaces the generated SQL.
- [ ] README frames problem → solution → pitch and links its Appendix-G section + chapters.
- [ ] Execution is read-only + row-limited + timed-out; verification runs before execution; composes patterns without forking.
- [ ] Question→answer eval set present and green.
