# 🧭 AI System-Design Doc — template

A **copy-into-your-repo design doc** that walks a system from *problem* to *architecture* the
way the book's method does: requirements → constraints → **back-of-envelope estimation** →
proposed architecture (with a C4-style diagram slot) → failure modes → alternatives → an
embedded ADR log → rollout. One Markdown file you fill in and circulate for review.

> This is **pure documentation** — no code, no secrets, no dependencies. There is nothing to
> build or run; you copy one file and start thinking. (Realizes book **Ch 42 — System Design
> for AI**; reused in Ch 27 and Ch 52.)

---

## When to copy it

- **Designing before you build.** You're about to build a feature or service and want the doc
  your team reviews *before* code exists, while the architecture is still cheap to change.
- **Prepping for a system-design interview.** The ten sections, in order, are a repeatable
  interview script (Ch 52): clarify requirements → estimate → sketch → stress the failure
  modes → name the trade-offs. Practise filling this out and you practise the interview.

Copy it into `docs/design/`, fill each section top-to-bottom, and circulate for review.

---

## Copy me

```bash
# 1. copy the template into your project's design folder (you own it now — not a submodule)
mkdir -p docs/design
cp templates/system-design-doc/system-design-template.md \
   docs/design/<kebab-feature-name>.md

# 2. fill it in top-to-bottom — every ▢ / TODO / <…> is a slot for you
grep -n "TODO" docs/design/<kebab-feature-name>.md   # or search  TODO  /  ▢  /  <…>  in your editor

# 3. circulate for review (open a PR with just the doc; reviewers comment inline)
git add docs/design/<kebab-feature-name>.md && git commit
```

Search for `TODO`, `▢`, and `<…>` — those are the only things you fill in. The
[`examples/agentic-feature-example.md`](examples/agentic-feature-example.md) is a short, fully
worked version of the same template so you can see what "filled in" looks like.

---

## What's in this folder

```text
system-design-doc/
├── README.md                  ← you are here (how to use it: design review + interview)
├── system-design-template.md  ← the doc to copy per design (the ten sections)
└── examples/
    └── agentic-feature-example.md  ← a short filled example ("add async batch runs")
```

When you copy this into your project, the file you keep is `system-design-template.md` (copied
per design into `docs/design/`). This `README.md` is the explainer — drop it or fold its notes
into your own contributor docs. The `examples/` doc is a reference; you don't copy it.

---

## The ten sections (and why this order)

| # | Section | The one job of this section |
|---|---|---|
| 1 | **Problem & goals** | What we're building and why — including explicit **non-goals**. |
| 2 | **Requirements** | Functional *and* non-functional. Latency, cost, availability, **and the AI ones**: token cost, eval thresholds, guardrails. |
| 3 | **Constraints & assumptions** | The fixed boundaries and the things you're taking on faith. |
| 4 | **Back-of-envelope estimation** | **Required.** QPS, tokens/req, $/req, storage, p95 — show the math. |
| 5 | **Proposed architecture** | Components + data flow, with a source-friendly diagram slot. |
| 6 | **Data model & APIs** | The entities and the contracts at the boundaries. |
| 7 | **Failure modes & risks** | What breaks, blast radius, mitigation — incl. injection & runaway loops. |
| 8 | **Alternatives** | Designs you rejected, and why — link out to ADRs. |
| 9 | **Decision log (ADRs)** | *Links* the immutable records; doesn't restate them. |
| 10 | **Open questions / rollout** | Unknowns, ramp plan, launch gate, success metrics. |

The order is deliberate: you can't size an architecture (§5) before you've estimated the load
(§4), and you can't estimate before you know the requirements (§2). Walking it in order is both
good design hygiene and a clean interview narrative.

---

## What makes this template opinionated

- **Requirements before architecture.** Non-functional requirements (latency / cost /
  availability / safety) are a first-class section, not a footnote — and the AI-specific ones
  (token cost, eval thresholds, guardrails) are prompted *explicitly* so you can't skip them.
- **Estimation is required.** §4 forces QPS / tokens / $ / p95 math up front — exactly the move
  the chapter and the interview reward. Round, illustrative numbers are fine; silence is not.
- **Links to ADRs, doesn't duplicate them.** §9 references records from
  [`../adr-template/`](../adr-template/PLAN.md) rather than re-arguing decisions inline.
- **Diagram in source form.** §5 has a marked slot for a C4 / Mermaid / Graphviz sketch you
  check in as source — never an opaque image you can't diff or regenerate.
- **Doubles as interview scaffolding.** The section order *is* a system-design interview script
  (Ch 52).
- **No code, no secrets.** It's a thinking artifact. The worked example uses illustrative
  numbers only — there's nothing to configure, so there's no `.env` here.

---

## How it composes with the rest of the repo

| This doc's section | Pairs with |
|---|---|
| §9 Decision log | [`../adr-template/`](../adr-template/PLAN.md) — one immutable record per decision |
| §2 / §7 eval thresholds & quality risks | [`../eval-dataset-template/`](../eval-dataset-template/PLAN.md) — the eval gate that backs them |
| §10 Launch gate | [`../production-readiness-checklist/`](../production-readiness-checklist/PLAN.md) — ticked before go-live |
| §5 Proposed architecture | the [`../../blueprints/`](../../blueprints/) — reference implementations to point §5 at |

---

## Definition of done (for your copy)

You're done when, in your repo's copy:

- [ ] Every `TODO` / `▢` / `<…>` placeholder is filled, or explicitly marked **N/A** with a reason.
- [ ] §4 shows real estimation math (QPS, tokens/req, $/req, a p95 latency budget).
- [ ] §5 has a real diagram (in source form), not the placeholder.
- [ ] §9 links the ADRs that back the hard-to-reverse choices.
- [ ] No secrets or proprietary data; any numbers carried over from the example are replaced.

See [`system-design-template.md`](system-design-template.md) for the template itself, and
[`examples/agentic-feature-example.md`](examples/agentic-feature-example.md) for a worked one.
