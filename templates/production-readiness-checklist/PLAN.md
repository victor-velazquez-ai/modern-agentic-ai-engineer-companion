# Template — Production-Readiness Checklist
> Realizes book Ch 41, 44 (from Appendix F) · Status: 📋 planned (Phase 1)

## What it scaffolds
A copy-into-your-repo go-live checklist for an agentic system — the book's Appendix F master
checklist as an actionable Markdown file, grouped by concern (reliability, security/safety,
evals, observability, cost, ops/runbook) with checkboxes you tick before you ship.

## When to copy it
You're about to put an agent in front of real users (or real money) and want a gate that
catches the things that actually break in production — prompt injection, no rollback, no
traces, unbounded cost — instead of finding them at 2 a.m. Copy it into the repo and require
it on the launch PR.

## Planned file tree
```text
production-readiness-checklist/
├── README.md                  # how to use it as a launch gate; "copy me"
└── PRODUCTION-READINESS.md    # the checklist itself, grouped (sections below)
```

`PRODUCTION-READINESS.md` section skeleton (checkbox items per group):
```markdown
# Production-Readiness Checklist — <service name>   (owner ▢ · target date ▢)
## Reliability        # health checks, timeouts, retries+backoff, graceful degradation, rollback
## Security & safety   # secrets in a manager (not code), authn/z, prompt-injection guards, PII handling
## Quality & evals     # eval gate green, thresholds defined, golden set covers launch scope
## Observability       # tracing on agent runs, logs structured, dashboards + alerts wired
## Cost & performance   # token budget + cap, semantic cache, p95 latency target, load tested
## Data & state        # migrations reversible, backups, retention/PII policy
## Ops & runbook       # on-call owner, runbook for top failures, kill switch / feature flag
## Sign-off            # ▢ eng · ▢ security · ▢ product
```

## Defaults baked in
- **Grouped by failure domain,** so a reviewer can reason concern-by-concern, not as one flat
  list — and so gaps are obvious.
- **AI-specific items are explicit:** prompt-injection defenses, an *eval gate that's green*,
  a token-cost cap, and tracing on agent runs sit alongside the classic SRE items.
- **Secrets item is non-negotiable:** "secrets come from a manager / env, never committed" is a
  checkbox, reflecting the repo-wide rule.
- **Cross-links the doers:** items point at the templates/blueprints that satisfy them
  (eval-gate → eval-dataset + CI; tracing → observability; rollback → terraform/compose).
- **Sign-off line:** named approvers (eng/security/product) so "ready" is a decision, not a vibe.
- **Pure Markdown, no secrets:** it's a gate document; ships filled-example-free or with a tiny sample.

## Maps to the book
- **Appendix F — Master Checklist:** this *is* that checklist, made copyable.
- **Ch 41 — Security, Safety & Compliance:** the injection/guardrail/PII items.
- **Ch 44 — Capstone End-to-End:** the production-readiness pass the capstone walkthrough runs
  before "done." **Cross-links:** [`../eval-dataset-template/`](../eval-dataset-template/PLAN.md)
  + [`../github-actions-ci/`](../github-actions-ci/PLAN.md) (eval gate),
  [`../../blueprints/observability-stack/`](../../blueprints/observability-stack/PLAN.md)
  (tracing), [`../system-design-doc/`](../system-design-doc/PLAN.md) (its risks section feeds this).

## Phase-2 definition of done
- [ ] `PRODUCTION-READINESS.md` is copyable; every item is a real, checkable action (no vagueness).
- [ ] Groups cover reliability, security/safety, evals, observability, cost, data, ops + sign-off.
- [ ] AI-specific items present: injection defense, eval gate, token cap, agent-run tracing.
- [ ] Items cross-link the template/blueprint that satisfies them; no secrets in the file.
