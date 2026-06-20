# Template — Architecture Decision Record (ADR)
> Realizes book Ch 27 (used in Ch 18, 50, 51, 54) · Status: 📋 planned (Phase 1)

## What it scaffolds
A single-file Markdown template for recording one architectural decision — context, the
decision, the alternatives considered, and the consequences — plus the `docs/adr/` folder
convention and an index so a project accumulates a readable decision log.

## When to copy it
You're making a choice that's expensive to reverse and someone (often future-you) will ask
"why did we do it this way?" — framework pick, datastore, sync vs async, build vs buy. Copy
the file, fill it in *at the moment of the decision*, and commit it with the change.

## Planned file tree
```text
adr-template/
├── README.md                  # how to use ADRs + numbering convention; "copy me"
├── 0000-adr-template.md       # the template to copy per decision (status/context/decision/…)
└── docs/
    └── adr/
        ├── README.md          # the index — table of ADRs by number, title, status
        └── 0001-example-record-architecture-decisions.md  # a filled example (the meta-ADR)
```

`0000-adr-template.md` skeleton:
```markdown
# ADR-NNNN: <short decision title>
- **Status:** ▢ Proposed | Accepted | Superseded by ADR-XXXX
- **Date:** YYYY-MM-DD   **Deciders:** ▢ names
## Context        # the forces, constraints, and problem (what makes this non-obvious)
## Decision       # the choice, stated as "We will…"
## Alternatives considered   # options weighed, with why each was rejected
## Consequences    # positive, negative, and follow-on work this creates
```

## Defaults baked in
- **One decision per file, immutable:** ADRs are append-only; you don't edit an Accepted ADR,
  you supersede it with a new one (`Status: Superseded by ADR-XXXX`).
- **Sequential numbering** `NNNN-kebab-title.md`; the `docs/adr/README.md` index lists them.
- **Lightweight (Nygard-style):** four sections, no ceremony — friction this low is the only
  reason teams keep writing them.
- **Alternatives are mandatory:** the section that makes an ADR worth more than a commit
  message is *why the roads not taken were rejected*.
- **Ships an example:** the first real ADR is "record architecture decisions," so the format
  demonstrates itself. No code, no secrets — pure documentation.

## Maps to the book
- **Ch 27 — Software Architecture Fundamentals:** ADRs as the unit of architectural memory
  (the chapter that introduces them).
- **Reused across the book:** Ch 18 (framework choice as an ADR), Ch 50/51 (the artifact a
  senior→architect produces), Ch 54 (decision records for a company/product). Referenced by
  [`../system-design-doc/`](../system-design-doc/PLAN.md) (its ADR log links out to these) and
  cross-linked from the career chapters as portfolio evidence.

## Phase-2 definition of done
- [ ] `0000-adr-template.md` is copyable as-is; all variable bits are `▢`/`<…>` placeholders.
- [ ] The example ADR (`0001-…`) is fully filled and validates the four-section format.
- [ ] `docs/adr/README.md` index renders as a clean table; numbering convention documented.
- [ ] No project-specific content or secrets in the template itself.
