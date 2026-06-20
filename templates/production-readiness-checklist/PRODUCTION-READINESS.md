# Production-Readiness Checklist — `<service name>` <!-- TODO: name the service -->

> **Launch gate.** Every box must be checked (or explicitly waived with a name + reason)
> before this service goes in front of real users or real money. Copy this file into your
> repo, fill the TODOs, and attach it to the launch PR. A box you *can't* check is a launch
> blocker until it's checked or waived.
>
> - **Owner:** ▢ `<name>` <!-- TODO -->
> - **Target launch date:** ▢ `<YYYY-MM-DD>` <!-- TODO -->
> - **Service / repo:** ▢ `<link>` <!-- TODO -->
> - **Reviewed against:** Appendix F (Master Checklist) · Ch 41 (Security, Safety & Compliance) · Ch 44 (Capstone)

How to read this: each group is a **failure domain**. Reason concern-by-concern, not as one
flat list — a gap in any single group can take the system down on its own. Items marked
**(AI)** are agent-specific and are the ones a generic SRE checklist misses. Items that point
at a `→ template/blueprint` are satisfied by copying that scaffold; follow the link.

---

## 1. Reliability

- [ ] **Health checks.** Liveness + readiness endpoints exist and are wired into the
      orchestrator (don't route traffic to a pod that isn't ready). → [`../fastapi-agent-service/`](../fastapi-agent-service/PLAN.md) (`/health`)
- [ ] **Timeouts everywhere.** Every outbound call (LLM, tools, DB, HTTP) has an explicit
      timeout. No unbounded waits — a hung model call must not hang the request.
- [ ] **Retries with backoff + jitter,** bounded to a max attempt count, and **only on
      idempotent / safe operations.** Retries never stampede a degraded dependency.
- [ ] **Graceful degradation.** Define what happens when the LLM / a tool / the vector store
      is down: a fallback model, a cached answer, or an honest "try again later" — never a 500
      and never a silent wrong answer.
- [ ] **Rollback path tested.** You can revert to the last-known-good deploy in one step and
      have done so at least once in staging. → [`../dockerfile-and-compose/`](../dockerfile-and-compose/PLAN.md) · [`../terraform-module/`](../terraform-module/PLAN.md)
- [ ] **Idempotency** on anything that writes or charges money (idempotency keys), so a retry
      or a double-click doesn't double-act.

## 2. Security & safety

- [ ] **Secrets come from a manager / env — never committed.** No keys, tokens, or
      connection strings in the repo or in images. Verified with a secret scanner in CI.
      *(Non-negotiable — repo-wide rule; see [`../../docs/CONVENTIONS.md`](../../docs/CONVENTIONS.md).)*
- [ ] **AuthN / AuthZ.** Every endpoint authenticates the caller and authorizes the action;
      no implicit "internal = trusted." Tool/agent actions run with least privilege.
- [ ] **(AI) Prompt-injection defenses.** Untrusted input (user text, tool/RAG output, web
      pages) cannot escalate privileges or exfiltrate data: system/user separation, tool
      allow-lists, output validation, and **no raw secrets in any prompt context.** → Ch 41
- [ ] **(AI) Tool / action guardrails.** Destructive or spend-capable tools require explicit
      confirmation or a policy check; the agent cannot call an unbounded shell / arbitrary URL.
- [ ] **PII handling.** PII is identified, minimized, encrypted in transit and at rest, and
      excluded from logs, traces, and prompts unless contractually allowed. → Ch 41
- [ ] **Dependency & image scanning** is green (no known-critical CVEs shipping to prod).
- [ ] **Rate limiting / abuse controls** on public entry points (per-user and global).

## 3. Quality & evals

- [ ] **(AI) Eval gate is green.** The offline eval suite runs in CI and **passes at the
      defined thresholds**; a regression blocks the merge/deploy.
      → [`../eval-dataset-template/`](../eval-dataset-template/PLAN.md) + [`../github-actions-ci/`](../github-actions-ci/PLAN.md)
- [ ] **(AI) Thresholds are defined and justified** (e.g. accuracy / faithfulness / pass-rate
      floors, max regression tolerance) — written down, not implicit.
- [ ] **(AI) Golden set covers the launch scope:** the happy paths, the known-hard cases, and
      the safety/refusal cases you actually care about — not just whatever was easy to collect.
- [ ] **Adversarial / red-team pass** for the top abuse and injection cases is recorded.

## 4. Observability

- [ ] **(AI) Tracing on agent runs.** Each run is traced end to end — prompts, tool calls,
      token counts, latency, and outcome — and you can pull up a single run by id.
      → [`../../blueprints/observability-stack/`](../../blueprints/observability-stack/PLAN.md)
- [ ] **Structured logs** (JSON, with a correlation/run id), no secrets or PII in log lines.
- [ ] **Dashboards** for the golden signals (latency, errors, throughput, saturation) **plus**
      the AI signals (token spend, eval-online scores, tool error rate).
- [ ] **Alerts wired** to a real on-call channel for: error-rate spike, p95 latency breach,
      cost-cap breach, and dependency-down — each with a documented response.

## 5. Cost & performance

- [ ] **(AI) Token budget defined + a hard cap enforced.** A per-request and per-tenant/day
      ceiling exists in code (not just a hope), and breaching it degrades safely rather than
      running up an unbounded bill. → Ch 41 / Appendix F
- [ ] **(AI) Semantic / response cache** in place where the workload repeats, with a sane TTL
      and a measured hit rate.
- [ ] **p95 latency target defined and met** under expected load (state the number here:
      `<p95 ms>` ▢ <!-- TODO -->).
- [ ] **Load tested** at expected peak (and 2× headroom); you know where it falls over and how.
- [ ] **Model/route choice justified** (cost vs. quality vs. latency) and cheap-path fallbacks
      configured.

## 6. Data & state

- [ ] **Migrations are reversible** (every forward migration has a tested `down`), and applied
      through the pipeline, not by hand.
- [ ] **Backups exist and a restore has been tested** (an untested backup is not a backup).
- [ ] **Retention / PII policy** is defined per data store: what's kept, how long, how it's
      deleted on request. → Ch 41
- [ ] **Vector store / memory** has a (re)build and eviction story; you can rebuild the index
      from source.

## 7. Ops & runbook

- [ ] **On-call owner named** for launch and the first week.
- [ ] **Runbook for the top failures** (LLM down, cost spike, bad deploy, poisoned context):
      symptom → check → action, written so the on-call who didn't build it can follow it.
- [ ] **Kill switch / feature flag.** You can disable the agent (or a specific tool) in
      seconds without a deploy.
- [ ] **Deploy is one command / one click** and documented; no tribal-knowledge launch steps.
- [ ] **Capacity & quota headroom** confirmed with every provider (LLM, infra) for launch load.

---

## Sign-off

"Ready" is a decision by named people, not a vibe. Each approver checks their box only when
**their** group above is fully green (or waived in writing).

- [ ] **Engineering** — ▢ `<name>` · `<date>` <!-- TODO -->
- [ ] **Security** — ▢ `<name>` · `<date>` <!-- TODO -->
- [ ] **Product** — ▢ `<name>` · `<date>` <!-- TODO -->

### Waivers (if any)

Any unchecked box that is *not* a launch blocker must be waived here, with an owner and a date
to fix it. An empty table means everything above is genuinely checked.

| Item | Why waived | Owner | Fix-by date |
|---|---|---|---|
| <!-- TODO: e.g. "Load tested at 2× peak" --> | <!-- reason --> | <!-- name --> | <!-- YYYY-MM-DD --> |
