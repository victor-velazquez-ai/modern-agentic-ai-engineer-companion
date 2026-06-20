# Template — AI System-Design Doc
> Realizes book Ch 42 (used in Ch 27, 52) · Status: 📋 planned (Phase 1)

## What it scaffolds
A single Markdown template that walks a design from problem to architecture the way the
book's method does: requirements → constraints → **back-of-envelope estimation** → proposed
architecture (with a C4-style sketch placeholder) → risks → an embedded ADR log.

## When to copy it
You're designing a feature or service before building it, writing the doc your team reviews —
or you're prepping for a system-design interview and want a repeatable structure to think in.
Copy it into `docs/design/`, fill each section, and circulate for review.

## Planned file tree
```text
system-design-doc/
├── README.md                  # how to use it (design review + interview); "copy me"
├── system-design-template.md  # the doc to copy per design (sections below)
└── examples/
    └── agentic-feature-example.md  # a short filled example (e.g. "add async batch runs")
```

`system-design-template.md` section skeleton:
```markdown
# Design: <system / feature name>
- **Author / Date / Status:** ▢
## 1. Problem & goals        # what we're building and why; non-goals
## 2. Requirements           # functional + non-functional (latency, availability, cost, safety)
## 3. Constraints & assumptions
## 4. Back-of-envelope estimation   # QPS, tokens/req, $/req, storage, p95 — show the math
## 5. Proposed architecture  # components + data flow; ▢ C4/diagram placeholder
## 6. Data model & APIs       # key entities, endpoints, contracts
## 7. Failure modes & risks   # what breaks, blast radius, mitigations
## 8. Alternatives            # other designs considered (link out to ADRs)
## 9. Decision log (ADRs)     # ▢ links to docs/adr/NNNN-*.md
## 10. Open questions / rollout
```

## Defaults baked in
- **Requirements before architecture:** non-functional reqs (latency/cost/availability/safety)
  are a first-class section, not an afterthought — the AI-specific ones (token cost, eval
  thresholds, guardrails) are prompted explicitly.
- **Estimation is required:** a back-of-envelope section forces QPS/tokens/$ math up front,
  exactly the move the chapter and interviews reward.
- **Links to ADRs, doesn't duplicate them:** §9 references
  [`../adr-template/`](../adr-template/PLAN.md) records rather than restating decisions.
- **Diagram placeholder, source-friendly:** a marked slot for a C4/Graphviz/Mermaid sketch.
- **Doubles as interview scaffolding:** the section order is a system-design interview script.
- **No code, no secrets:** it's a thinking artifact; the example uses illustrative numbers only.

## Maps to the book
- **Ch 42 — System Design for AI:** the design method + estimation this template operationalizes.
- **Reused:** Ch 27 (quality attributes, C4, ADRs feed §5/§9), Ch 52 (system-design interview
  drills use this structure). **Notebook:** the
  [`learn/part-11-…/42-system-design-for-ai/`](../../learn/) worksheet fills this out.
  **Templates:** composes [`../adr-template/`](../adr-template/PLAN.md); pairs with
  [`../production-readiness-checklist/`](../production-readiness-checklist/PLAN.md) at launch.

## Phase-2 definition of done
- [ ] `system-design-template.md` is copyable; every section has a one-line prompt + `▢` slots.
- [ ] The filled `examples/` doc shows real estimation math and links a sample ADR.
- [ ] Section order matches the book's Ch 42 method and works as an interview script (Ch 52).
- [ ] No secrets/proprietary data; numbers in the example are clearly illustrative.
