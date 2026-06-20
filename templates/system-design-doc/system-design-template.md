<!--
  COPY THIS FILE per design:  cp system-design-template.md docs/design/<kebab-name>.md
  Then work top-to-bottom, replacing every  ▢  and  <…>  placeholder. Each section has a
  one-line prompt telling you what belongs there. The section order is also a system-design
  interview script (Ch 52) — you can talk it through in the same order.
  Delete this comment when you fill it in. No secrets, no code — this is a thinking artifact.
-->

# Design: <system / feature name>

- **Author:** ▢ name   **Date:** YYYY-MM-DD   **Status:** ▢ Draft | In review | Approved | Superseded
- **Reviewers:** ▢ names   **Related docs:** ▢ links (PRD, tickets, prior designs)

> One-paragraph summary: ▢ in 2–3 sentences, what is this and why does it need a design doc?
> A reader should know whether this concerns them before reading section 1.

---

## 1. Problem & goals

<!-- What we're building and why. State the user/business problem first, then the goals.
     Be explicit about NON-goals — they prevent scope creep and frame the review. -->

- **Problem:** ▢ TODO — the concrete pain or opportunity, stated from the user's point of view.
- **Goals:** ▢ TODO — what success looks like (bullet the outcomes, not the implementation).
- **Non-goals:** ▢ TODO — what this deliberately does *not* do (just as important as the goals).

## 2. Requirements

<!-- Functional = what it must do. Non-functional = how well. Non-functional reqs are a
     first-class section here, NOT an afterthought — they shape the architecture in §5.
     Fill in concrete numbers; "fast" and "cheap" are not requirements, "p95 < 2s" is. -->

**Functional**

- ▢ TODO — the capabilities the system must provide (bullet list).

**Non-functional** (give a target for each that applies; delete the rest)

| Attribute | Target | Notes |
|---|---|---|
| Latency (p50 / p95) | ▢ e.g. p95 < 2.0 s | end-to-end, user-perceived |
| Availability | ▢ e.g. 99.9% | and the SLO window |
| Throughput | ▢ e.g. 50 QPS peak | sustained vs burst |
| Token cost / request **(AI)** | ▢ e.g. ≤ $0.01/req | the unit economics — see §4 |
| Eval quality threshold **(AI)** | ▢ e.g. ≥ 0.90 pass rate | the gate that blocks release — see [`../eval-dataset-template/`](../eval-dataset-template/PLAN.md) |
| Guardrails / safety **(AI)** | ▢ e.g. injection + PII + output filter | what must be enforced, and where |
| Privacy / data residency | ▢ e.g. no PII to 3rd-party model | regulatory constraints |
| Scale horizon | ▢ e.g. 10× in 12 months | what you're designing headroom for |

> **AI-specific reqs are mandatory to consider.** Token cost, eval thresholds, and guardrails
> are the requirements a generic template forgets — name them explicitly even if the answer is
> "N/A for this design," so the reviewer sees you thought about them.

## 3. Constraints & assumptions

<!-- The fixed boundaries you must design within (constraints) and the things you're taking as
     true without proof (assumptions). Surfacing assumptions early is how a reviewer catches the
     wrong one before you build on it. -->

- **Constraints:** ▢ TODO — fixed facts (existing stack, budget, deadline, compliance, vendor).
- **Assumptions:** ▢ TODO — what you're treating as true (load shape, model availability, data quality).
- **Dependencies:** ▢ TODO — upstream systems/teams/models this relies on.

## 4. Back-of-envelope estimation

<!-- REQUIRED. Show the math. QPS, tokens/request, $/request, storage, and a p95 sketch. This
     is the move the chapter and the interview reward: order-of-magnitude numbers, derived in the
     open, before any architecture. Use illustrative round numbers — being roughly right beats
     being precisely silent. -->

▢ TODO — work the numbers. A worked skeleton (replace with yours):

```
Traffic
  daily active requests   : ▢  R  = 100,000 req/day
  peak factor             : ▢  ~5× average  → peak QPS ≈ R / 86,400 × 5 ≈ 6 QPS
Per-request LLM cost
  tokens in / out         : ▢  1,500 in + 500 out = 2,000 tokens/req
  blended price           : ▢  $X per 1M tokens   → $/req ≈ 2,000 / 1e6 × $X
  cost/day                : ▢  R × $/req = $____   (does this fit the §2 cap?)
Latency budget (p95 target from §2 = ▢ 2.0 s)
  retrieval               : ▢  ~150 ms
  model call              : ▢  ~1,200 ms   (dominant term — the thing to optimize)
  post-processing/guards  : ▢  ~100 ms
  headroom                : ▢  ~550 ms
Storage / state
  vectors / rows / req    : ▢  N docs × D dims × 4 bytes = ____ ; growth/month = ____
```

> **Sanity check:** does cost/day fit the budget in §3? Does the latency sum fit the p95 in §2?
> If not, that tension is the most important thing for §5 to resolve — say so here.

## 5. Proposed architecture

<!-- Components + data flow. Lead with the happy path, then call out the interesting edges.
     Keep the diagram in SOURCE form (Mermaid / Graphviz / a C4 sketch) so it diffs and
     regenerates — never paste an opaque image you can't edit. -->

▢ TODO — describe the components and how a request flows through them.

```text
▢ C4 / architecture diagram placeholder — replace with a real diagram.

  Recommended (source-friendly, renders on GitHub): a Mermaid block, e.g.

  ```mermaid
  flowchart LR
    user([User]) --> api[API / gateway]
    api --> agent[Agent orchestrator]
    agent --> retr[(Retrieval / vector store)]
    agent --> model{{LLM}}
    agent --> tools[Tools / external APIs]
    agent --> obs[/Traces + metrics/]
  ```

  Or a C4 Context/Container sketch (see Ch 27), or a Graphviz .dot checked in next to this doc.
  Keep the rendered image out of version control; commit the source.
```

- **Key components:** ▢ TODO — one line each on responsibility and why it exists.
- **Data flow:** ▢ TODO — the request lifecycle, numbered steps, including the failure branches.

## 6. Data model & APIs

<!-- The key entities and the contracts at the boundaries. Just enough to review the design —
     not the full schema. Pin down the shapes that are expensive to change later. -->

- **Entities:** ▢ TODO — the few core objects and their important fields/relationships.
- **APIs / contracts:** ▢ TODO — the endpoints or interfaces (method, path, request → response).
  Note idempotency, versioning, and what's a breaking change.

```
▢ e.g.
POST /v1/runs        body: { input, context_id? }   → 202 { run_id }
GET  /v1/runs/{id}                                   → 200 { status, output, usage }
```

## 7. Failure modes & risks

<!-- What breaks, the blast radius, and the mitigation. Be specific: "the model API times out"
     not "things could fail". For AI systems include the AI-native failure modes —
     hallucination, prompt injection, runaway loops, cost blowups. -->

| Failure mode | Likelihood | Blast radius | Mitigation |
|---|---|---|---|
| ▢ Model API timeout / 5xx | ▢ med | ▢ requests stall | ▢ retries w/ backoff, fallback model, circuit breaker |
| ▢ Prompt injection **(AI)** | ▢ med | ▢ data exfil / tool misuse | ▢ input/output guardrails, tool allow-list, least privilege |
| ▢ Runaway agent loop **(AI)** | ▢ low | ▢ cost + latency spike | ▢ step/iteration cap, token budget per run, kill switch |
| ▢ Retrieval returns junk | ▢ med | ▢ wrong answers | ▢ eval gate, relevance threshold, "I don't know" path |
| ▢ <your risk> | ▢ | ▢ | ▢ |

## 8. Alternatives

<!-- Other designs you genuinely considered, and why this one won. This is the section that
     proves the decision was a choice, not the first thing that came to mind. Link out to ADRs
     rather than restating the full trade-off here. -->

- **▢ Alternative A** — <what it was>. Not chosen because <reason>. (See ADR ▢.)
- **▢ Alternative B** — <what it was>. Not chosen because <reason>. (See ADR ▢.)

## 9. Decision log (ADRs)

<!-- This doc REFERENCES decisions; it does not duplicate them. Significant, hard-to-reverse
     choices get their own immutable record under docs/adr/. Link them here. -->

▢ TODO — link the records that back this design:

- [ADR-0001 — ▢ title](../../docs/adr/0001-▢.md) — ▢ one-line what it decided.
- [ADR-0002 — ▢ title](../../docs/adr/0002-▢.md) — ▢ one-line what it decided.

> New to ADRs? Use [`../adr-template/`](../adr-template/PLAN.md) — one decision per file
> (Context · Decision · Alternatives · Consequences), committed with the change it describes.

## 10. Open questions / rollout

<!-- What you don't know yet, and how this actually ships. Naming the unknowns is a sign of a
     mature design, not a weak one. -->

- **Open questions:** ▢ TODO — the things still unresolved, with an owner for each.
- **Rollout plan:** ▢ TODO — flagged? shadow traffic? % ramp? rollback trigger?
- **Launch gate:** ▢ TODO — link the [`../production-readiness-checklist/`](../production-readiness-checklist/PLAN.md) you'll tick before go-live.
- **Metrics of success:** ▢ TODO — how you'll know post-launch whether the goals in §1 were met.
