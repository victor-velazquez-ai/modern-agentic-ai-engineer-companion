# 📐 Architecture Decision Record (ADR) — template

A tiny, copy-into-your-repo convention for recording **one architectural decision per file**:
the *context* that forced a choice, the *decision* you made, the *alternatives* you weighed,
and the *consequences* you accepted. Over time these accumulate into `docs/adr/` — a readable
decision log that answers the question every codebase eventually gets: *"why did we do it this
way?"*

> This is **pure documentation** — no code, no secrets, no dependencies. There is nothing to
> build or run; you copy two files and start writing. (Realizes book **Ch 27 — Software
> Architecture Fundamentals**; reused in Ch 18, 50, 51, 54.)

---

## Copy me

```bash
# 1. copy the ADR convention into your project
cp templates/adr-template/0000-adr-template.md      <your-repo>/docs/adr/
cp -r templates/adr-template/docs/adr/README.md     <your-repo>/docs/adr/   # the index
#   (the example 0001-… is optional — keep it as a worked example or delete it)

# 2. for each decision worth recording:
cp docs/adr/0000-adr-template.md docs/adr/0001-<kebab-title>.md
#   fill in every ▢ / <…> placeholder, then add a row to docs/adr/README.md

# 3. commit the ADR *with the change it describes*
git add docs/adr/0001-<kebab-title>.md && git commit
```

Search for `TODO`, `▢`, and `<…>` — those are the only things you fill in.

---

## When to write one

You're making a choice that is **expensive to reverse** and someone (often future-you) will
ask why: a framework pick, a datastore, sync vs async, build vs buy, an auth model, a wire
format. Write the ADR **at the moment of the decision**, while the alternatives and the
reasons are still fresh, and commit it alongside the change that implements it.

You do **not** need an ADR for reversible, low-stakes choices (a variable name, a lint rule).
The bar is roughly: *"if we got this wrong, would unwinding it cost more than a day?"*

---

## Numbering & naming convention

- Files are named `NNNN-kebab-title.md`, e.g. `0007-use-postgres-for-the-eval-store.md`.
- `NNNN` is a **zero-padded, monotonically increasing** integer. `0000` is reserved for the
  blank template; real decisions start at `0001`.
- Numbers are **never reused**. If a decision is reversed you do not delete or renumber its
  ADR — you write a **new** ADR and mark the old one `Superseded by ADR-XXXX`.
- The title is a short noun phrase describing the decision, kebab-cased.

## The rule: ADRs are immutable

An accepted ADR is a historical record, not a living document. **Do not edit the substance of
an Accepted ADR.** When reality changes:

- **Reverse / replace a decision** → write a new ADR and set the old one's status to
  `Superseded by ADR-XXXX`; set the new one's `Context` to reference the one it replaces.
- **Small clarification / typo** → fine to fix in place; don't rewrite the reasoning.

This append-only discipline is what makes the log trustworthy: a reader can trust that an ADR
says what was actually decided *at the time*, not a back-edited version.

## The four sections (Nygard-style)

Kept deliberately lightweight — four sections, no ceremony. Friction this low is the only
reason teams keep writing them.

| Section | What goes here |
|---|---|
| **Context** | The forces, constraints, and problem — what makes this decision non-obvious. |
| **Decision** | The choice, stated affirmatively: *"We will…"* |
| **Alternatives considered** | Each option weighed **and why it was rejected** (mandatory). |
| **Consequences** | What this makes easier, what it makes harder, and the follow-on work. |

> **Alternatives are mandatory.** The "alternatives considered" section is the one thing that
> makes an ADR worth more than a commit message — *why the roads not taken were rejected* is
> the part future-you actually needs.

---

## What's in this folder

```text
adr-template/
├── README.md                  ← you are here (how to use ADRs + the convention)
├── 0000-adr-template.md       ← the blank template; copy this per decision
└── docs/
    └── adr/
        ├── README.md          ← the index (table of ADRs by number / title / status)
        └── 0001-example-record-architecture-decisions.md   ← a filled worked example
```

When you copy this into your project, the part you keep is `docs/adr/` (the index + your
records) plus the blank `0000-adr-template.md` to copy from. This top-level `README.md` is the
explainer — you can drop it or fold its conventions into your own contributor docs.

## Further reading

- Michael Nygard, *"Documenting Architecture Decisions"* (2011) — the original four-section
  format this template follows.
- [adr.github.io](https://adr.github.io/) — tools and variants if you outgrow plain Markdown.
- Cross-linked in this repo from [`../system-design-doc/`](../system-design-doc/PLAN.md) (its
  ADR log links out to records like these).
