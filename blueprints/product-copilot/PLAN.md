# Blueprint — Customer-Facing Product Copilot  (solution)

> Appendix G use case · Status: 📋 planned (Phase 1)

## The problem it solves
Product friction: users do not discover features, get stuck during onboarding, or churn
before reaching value. Product and growth teams want better activation, stickiness, and
reduced friction — value delivered inside the moment of use, not a separate "AI product."

## What it does
An assistant embedded *inside* a product — an in-app copilot that helps users get value:
onboarding guidance, in-context help, performing actions on the user's behalf, and answering
questions about their own data in the app. Its defining constraints (Ch 43 customer-facing
copilot): **latency is a product feature, unit economics must fit the subscription margin,
abuse resistance on a public surface, and strict multi-tenant isolation**. Tools are scoped
to the signed-in user's session — never a privileged service identity (Appendix G →
"Customer-facing product copilot").

## Composes (pattern blueprints used)
- [`../agent-loop/`](../agent-loop/) — the in-app agent that answers and acts as the authenticated user (Ch 12).
- [`../rag-pipeline/`](../rag-pipeline/) — retrieval over product docs and the user's own *scoped* data (Ch 13).
- [`../llm-gateway/`](../llm-gateway/) — tiered routing + provider fallback + aggressive caching (prompt-prefix, exact, semantic) and per-user limits to protect cost and margin (Ch 39, 40).
- [`../eval-harness/`](../eval-harness/) — evals + online feedback as a first-class product metric (Ch 22).
- [`../observability-stack/`](../observability-stack/) — latency, cost-per-user, and abuse signals on the public surface.

## Planned structure
```text
product-copilot/
├── README.md
├── PLAN.md
├── app/
│   ├── copilot_api.py        # stateless streaming SSE agent API behind the gateway (Ch 25, 39)
│   ├── session_tools.py      # tools act ONLY as the authenticated user, per tenant (Ch 12, 41)
│   └── guardrails.py         # abuse detection + front-door guardrails on a public surface (Ch 41)
├── tenancy/
│   └── scope.py              # per-user + per-tenant isolation on retrieval and tools
├── evals/
│   └── copilot_golden.jsonl  # task-success + feedback-loop checks
├── data/
│   └── product_docs/         # ~6 product-doc snippets + 2 mock tenants' scoped data
└── demo.py                   # MOCK: same query, two tenants → isolated, scoped results
```

## Maps to the book
- **Appendix G:** "Customer-facing product copilot" (in-app RAG + scoped tools; buyer = Product/growth).
- **Chapters showcased:** 25/39 (stateless streaming SSE API + model gateway), 13 (product +
  scoped-data retrieval), 12/41 (per-user tools, guardrails, abuse detection), 40 (caching +
  per-user limits = margin engineering), 38 (polished streaming UI), 22 (evals + online
  feedback), 43 (customer-facing copilot constraints).

## How to adapt it
- Replace `data/product_docs/` with your product knowledge; wire `session_tools.py` to your real per-user actions.
- **Scope everything per user and per tenant** — cross-tenant leakage through a mis-scoped tool or cache is catastrophic.
- Treat cost per user per month as a hard product budget: tune caching + per-user limits (cost engineering *is* product engineering here).
- Harden `guardrails.py` — a public prompt surface will be attacked for sport.
- Make online feedback a first-class metric alongside offline evals.

## Phase-2 definition of done
- [ ] `demo.py` runs in MOCK mode; the same query under two tenants returns isolated, scoped results.
- [ ] README frames problem → solution → pitch and links its Appendix-G section + chapters.
- [ ] Per-user/per-tenant scoping enforced on retrieval + tools; caching/limits present; composes patterns (esp. llm-gateway) without forking.
- [ ] Abuse guardrails on the public surface; eval + feedback hook present.
