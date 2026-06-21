# 🧩 Product Copilot — a customer-facing, in-app copilot (solution blueprint)

> **Appendix G use case #11** · *Customer-facing product copilot* · Buyer: Product / Growth
> Status: ✅ Phase 2 — runnable in MOCK mode (no API spend).

A **solution** blueprint: a real, end-to-end agentic product assembled by **composing the pattern
blueprints** (the parts) — it does not fork or reimplement them. Everything runs **offline,
deterministically, and for $0** under `COMPANION_MOCK=1` (the repo default).

```bash
python demo.py                    # offline, deterministic, zero API spend
COMPANION_MOCK=0 python demo.py   # routes generation through the live llm-gateway (needs a key)
```

---

## Problem

Product friction is expensive: users don't discover features, get stuck in onboarding, or churn
before they reach value. Product and growth teams don't want *another* separate "AI product" — they
want value delivered **inside the moment of use**: better activation, stickiness, and less friction,
right where the user already is.

## Solution

An assistant embedded **inside** the product — an in-app copilot that helps the signed-in user get
value: onboarding guidance, in-context help, answering questions about **their own data**, and
performing low-risk actions **on their behalf**. On a public, multi-tenant surface its defining
constraints (Ch 43) are different from an internal tool's:

| Constraint | Why it's a product feature | Where it lives here |
|---|---|---|
| **Strict multi-tenant isolation** | Cross-tenant leakage is catastrophic and silent | `tenancy/scope.py` — one **isolated retrieval index per tenant** (isolation *by construction*, not a `WHERE` clause) |
| **Tools scoped to the signed-in user** | A public model surface must never act as a privileged service identity | `app/session_tools.py` — tools **close over the verified session**; the model never names an identity |
| **Abuse resistance** | A public prompt box will be attacked for sport | `app/guardrails.py` — content guard (injection/PII via the gateway) **+ per-user rate limit** |
| **Unit economics fit the margin** | Cost-per-user-per-month is a hard product budget | `llm-gateway` routing + **exact/semantic cache** + **per-(tenant,user) metering** |
| **Latency** | Streaming is the difference between "fast" and "slow" | `Copilot.stream()` — token-by-token SSE-style output |

### How it composes the pattern blueprints

The whole request path is five pattern blueprints wired together (imported from their sibling
`src/` via `app/_compose.py` — **one copy of each, never forked**):

```
                              ┌────────────────────────────────────────────────────────────┐
  user message  ─▶  FrontDoor │ rate-limit  ─▶  content guard (injection/PII)               │  ← app/guardrails.py  → llm-gateway Guard (Ch 41)
                              └───────────────────────────────┬────────────────────────────┘
                                                              ▼  (blocked? friendly refusal, $0)
                    TenantStores.retrieve(session, q)  ─▶  rag-pipeline hybrid search        ← tenancy/scope.py → rag-pipeline (Ch 13)
                    (ONLY this tenant's index)                │
                                                              ▼
                    AgentLoop(model=gateway-backed, tools=session-scoped)                    ← agent-loop (Ch 12)
                      ├─ tool turn? → get_my_orders / get_order_status / set_notifications   ← app/session_tools.py (acts AS the user)
                      └─ answer turn → Gateway.complete(prompt+evidence, label=tenant/user)  ← llm-gateway (Ch 39–40: route+cache+meter)
                                                              │
                                                              ▼
                    CopilotReply{ text, citations, tool, cost_usd, cached, model }           ← structured, auditable output (Ch 15)
                                                              │
                    (whole turn wrapped in one trace: run▸guard▸retrieval▸agent▸model)       ← observability-stack (Ch 23)
```

| Composed pattern | Role in the copilot | Chapter |
|---|---|---|
| [`agent-loop`](../agent-loop/) | The in-app agent: observe→decide→act, answers and acts **as the authenticated user** | 12 |
| [`rag-pipeline`](../rag-pipeline/) | Retrieval over product docs **and** the user's own *scoped* data | 13 |
| [`llm-gateway`](../llm-gateway/) | Tiered routing + fallback + **caching** + **per-user metering** + content **guards** | 39–41 |
| [`eval-harness`](../eval-harness/) | The golden set that gates a prompt/model change + the online-feedback hook | 22 |
| [`observability-stack`](../observability-stack/) | Latency, cost-per-user, and abuse signals as a trace tree | 23 |

---

## What the demo shows

`python demo.py` walks the full surface, all offline and deterministic:

1. **Isolation** — the *same* question under two tenants (`acme/alice`, `globex/bob`) returns
   *scoped, isolated* answers. Assertions prove Acme never sees Globex's private code phrase and
   vice-versa. **This is the headline definition of done.**
2. **Scoped RAG** — a product-doc question answered from shared docs, with citations.
3. **Scoped tool** — "show my orders" lists *only the signed-in user's* orders.
4. **Abuse guardrail** — a prompt-injection attempt is blocked at the front door, $0 spent.
   **4b. Abuse bound** — a per-user rate limit cuts off a flood after its budget.
5. **Margin** — per-`(tenant,user)` cost metering; a repeat question is served from cache for $0.
6. **Streaming** — the answer streamed token-by-token.
7. **Observability** — one turn rendered as a trace tree with a cost roll-up.
8. **Evals** — the golden set (`evals/copilot_golden.jsonl`) run through the eval-harness with a
   per-tag breakdown (`task-success`, `isolation`, `abuse`, `scoped-data`, `feedback`).

---

## Files

```text
product-copilot/
├── README.md                     # this file
├── PLAN.md                       # the spec (unchanged)
├── demo.py                       # MOCK: same query, two tenants → isolated, scoped results
├── app/
│   ├── _compose.py               # composition seam: put sibling pattern src/ on sys.path
│   ├── copilot_api.py            # stateless per-request agent behind the gateway (Ch 12/25/39)
│   ├── session_tools.py          # tools act ONLY as the authenticated user, per tenant (Ch 12/41)
│   └── guardrails.py             # front-door: per-user rate limit + gateway content guard (Ch 41)
├── tenancy/
│   └── scope.py                  # per-tenant isolated retrieval + the Session identity (Ch 41/43)
├── evals/
│   └── copilot_golden.jsonl      # task-success + isolation + abuse + feedback checks
└── data/
    ├── product_docs/             # 6 shared product-doc snippets (the "Nimbus" help center)
    └── tenants/{acme,globex}/    # 2 mock tenants' PRIVATE runbooks (the isolation fixtures)
```

---

## How to adapt it to your domain

- **Replace the corpus.** Swap `data/product_docs/` for your product's knowledge and
  `data/tenants/<id>/` for each tenant's private docs. Keep the metadata shape (`tenant_id`,
  `visibility`, `title`).
- **Wire `session_tools.py` to your real per-user actions.** Replace the in-memory `UserDataStore`
  with calls to your product API. **Keep the bind-to-session shape**: the tool closes over the
  verified `Session`, so the model can never name whose data it touches.
- **Scope *everything* per user and per tenant.** Cross-tenant leakage through a mis-scoped tool or
  cache is catastrophic. Here, isolation is structural: one index per tenant
  (`tenancy.TenantStores`) and a cache label salted per `(tenant, user)`
  (`tenancy.tenant_cache_label`). Swap the in-memory store for a Chroma collection / Pinecone
  namespace **named for the tenant** — the shape is unchanged.
- **Treat cost-per-user-per-month as a hard budget.** Tune the gateway's caching and the
  `RateLimiter` budget by plan tier (`Session.plan`). Cost engineering *is* product engineering
  here.
- **Harden `guardrails.py`.** A public prompt surface will be attacked. The content guard composes
  the gateway's `Guard`; swap the rate limiter for Redis/token-bucket and the detectors for a real
  classifier/DLP service — the seams don't change.
- **Make online feedback a first-class metric.** Log a thumbs-up/down per reply id and trend it
  next to the offline `eval-harness` scores. Ship a prompt/model change only when **both** clear
  the bar.

---

## Maps to the book

- **Appendix G:** "Customer-facing product copilot" (in-app RAG + scoped tools; buyer =
  Product/growth).
- **Chapters showcased:** 25/39 (stateless streaming API + model gateway), 13 (product +
  scoped-data retrieval), 12/41 (per-user tools, guardrails, abuse detection), 40 (caching +
  per-user limits = margin engineering), 22 (evals + online feedback), 43 (customer-facing copilot
  constraints).

> **Study & adapt, not copy-paste.** Like every blueprint, this is the "how a senior would
> structure it" reference you lift ideas from — read it *by running it*, then build your own.
