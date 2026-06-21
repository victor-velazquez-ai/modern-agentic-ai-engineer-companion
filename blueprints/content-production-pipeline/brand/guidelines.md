# Brand voice + product facts — the grounding corpus (sample)

This file is the **retrieval corpus** the pipeline grounds every draft on (via the
`rag-pipeline` blueprint). It is deliberately small and fictional: a made-up company,
**Northwind Analytics**, selling a product called **PulseBoard**. Replace the whole file
with *your* brand voice + product truth and the pipeline adapts with no code change — this
is the "swap `brand/guidelines.md`" step in the PLAN.

Two kinds of content live here, and both matter:

- **Brand voice** — *how* we are allowed to sound. The critique pass and the guardrails read
  this; it is what keeps output on-brand instead of bland-at-scale.
- **Product facts** — *what is true*. The draft stage may only assert claims that trace back
  to a fact below. A claim with no supporting fact is exactly what the guardrails flag, and
  what the factual evals catch.

The retriever chunks this on blank lines / headings, so keep each fact a self-contained
sentence or two.

## Brand voice

Northwind Analytics speaks plainly and with measured confidence. We are a calm expert, not a
hype machine. We prefer concrete numbers to superlatives, and we never promise outcomes we
cannot evidence.

Our tone is helpful and direct: short sentences, active voice, no jargon for its own sake. We
write for busy data and operations leaders who want the point first.

We do not shout. We avoid exclamation marks, ALL-CAPS, and words like "revolutionary",
"miracle", or "best in the world". Trust is earned with evidence, not adjectives.

When we mention performance, results, or anything a customer's finance or legal team would
scrutinize, we attach the qualifier that it varies by setup and we cite a source. Honesty is a
feature, not a constraint.

## Product facts — PulseBoard

PulseBoard is a self-serve analytics dashboard for operations teams. It connects to your
existing data warehouse; there is no data migration required to get started.

PulseBoard ships with more than forty prebuilt metric templates for common operations
workflows, so most teams see their first live dashboard within a day of connecting a source.

In a 2025 customer survey of 180 teams, the median team reported cutting weekly reporting time
from about six hours to under one hour after adopting PulseBoard. Results vary by team size and
data maturity.

PulseBoard is SOC 2 Type II certified and encrypts data in transit and at rest. It never trains
any model on customer data.

Pricing is per active editor, billed monthly, with a free read-only viewer tier so the whole
team can see dashboards without a per-seat cost.

PulseBoard integrates with Snowflake, BigQuery, Postgres, and Redshift today. A Databricks
connector is on the public roadmap but is not yet generally available.

## Compliance notes

Any marketing that mentions performance, returns, or time-savings figures must keep the figure
attached to its survey context ("median team", "results vary") — never round it up into an
absolute promise.

The required disclaimer for any content that touches investment or returns language is:
"Past performance does not guarantee future results."
