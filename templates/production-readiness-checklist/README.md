# Production-Readiness Checklist — template

A **copy-into-your-repo go-live gate** for an agentic system. It's the book's
**Appendix F master checklist** made actionable: a single Markdown file, grouped by failure
domain, with checkboxes you tick before you put an agent in front of real users or real money.

Use it to catch the things that *actually* break agents in production — prompt injection, no
rollback, no traces, an unbounded token bill — at review time, instead of at 2 a.m.

> **Realizes** Appendix F (Master Checklist) · Ch 41 (Security, Safety & Compliance) ·
> Ch 44 (Capstone end-to-end). Pure Markdown — **no code, no secrets.**

---

## What's in here

```text
production-readiness-checklist/
├── README.md                  # you are here — how to use it as a launch gate
└── PRODUCTION-READINESS.md    # the checklist itself, grouped by failure domain
```

The checklist groups are: **Reliability · Security & safety · Quality & evals ·
Observability · Cost & performance · Data & state · Ops & runbook · Sign-off.** Each group is
a concern a reviewer can reason about on its own. AI-specific items — prompt-injection
defenses, a *green* eval gate, a token-cost cap, and tracing on agent runs — are marked
**(AI)** and sit right alongside the classic SRE items, because a generic checklist misses them.

---

## Copy me

```bash
# 1. copy the checklist into your service repo (you own it now — not a submodule)
cp templates/production-readiness-checklist/PRODUCTION-READINESS.md \
   ~/work/my-service/PRODUCTION-READINESS.md

# 2. fill the placeholders: service name, owner, target date, p95 target, approvers
grep -n "TODO" ~/work/my-service/PRODUCTION-READINESS.md   # or search TODO / ▢ in your editor
```

Then make it a **gate**, not a doc that rots:

1. **Require it on the launch PR.** Paste the checklist into the go-live PR description (or
   commit the filled file) so every box is reviewed in the open.
2. **Tick boxes only when they're truly true.** A box you can't honestly check is a launch
   blocker — fix it, or record a **waiver** (owner + fix-by date) in the table at the bottom.
3. **Get the three sign-offs.** Engineering, Security, and Product each check their box only
   when *their* group is fully green. "Ready" is a decision by named people, not a vibe.

---

## How the items get satisfied

Many items point at another scaffold in this repo that *implements* them — follow the link in
the checklist:

| Checklist item | Satisfied by |
|---|---|
| Eval gate is green / thresholds defined | [`../eval-dataset-template/`](../eval-dataset-template/PLAN.md) + [`../github-actions-ci/`](../github-actions-ci/PLAN.md) |
| Tracing on agent runs / dashboards / alerts | [`../../blueprints/observability-stack/`](../../blueprints/observability-stack/PLAN.md) |
| Rollback path / one-command deploy | [`../dockerfile-and-compose/`](../dockerfile-and-compose/PLAN.md) · [`../terraform-module/`](../terraform-module/PLAN.md) |
| Health endpoints | [`../fastapi-agent-service/`](../fastapi-agent-service/PLAN.md) |
| Injection defenses / PII / token cap | Ch 41 (the design); this checklist is the gate |
| Risks feed the checklist | [`../system-design-doc/`](../system-design-doc/PLAN.md) (its risks section) |

This checklist doesn't *do* any of that work — it's the gate that verifies the work is done.
It contains **no business logic and no secrets**: secrets always come from a manager / env and
are never committed (see [`../../docs/CONVENTIONS.md`](../../docs/CONVENTIONS.md)). There's no
`.env` here because there's nothing to configure — it's a document you fill in and review.

---

## Definition of done (for your copy)

You're done when, in your repo's copy:

- [ ] Every `TODO` / `▢` placeholder is filled (service name, owner, date, p95 target, approvers).
- [ ] Every box is either checked or has a waiver row (owner + fix-by date).
- [ ] All three sign-off boxes are checked by named approvers.
- [ ] The filled checklist is attached to the launch PR.

See [`PRODUCTION-READINESS.md`](PRODUCTION-READINESS.md) for the checklist itself.
