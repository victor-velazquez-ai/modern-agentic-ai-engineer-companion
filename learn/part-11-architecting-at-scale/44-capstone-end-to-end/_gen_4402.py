"""Generator for 44-02-production-readiness-pass.ipynb (worksheet).

Builds a valid nbformat-4 notebook. Run from this folder:
    python _gen_4402.py
This script is a build tool; the notebook is the deliverable.
"""
import json

cells = []


def md(text: str):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": _lines(text)})


def code(text: str):
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _lines(text),
    })


def _lines(text: str):
    text = text.strip("\n")
    raw = text.split("\n")
    return [line + "\n" for line in raw[:-1]] + [raw[-1]]


# 1. Title + header -----------------------------------------------------------
md(r"""
# Production-readiness pass — harden it, then run the master checklist

> 📓 *Companion to* **Modern Agentic AI Engineer** · Ch 44 §§44.2–44.5 · type: worksheet

**The promise:** by the end you can take the capstone (or your own system) through the book's **master production-readiness checklist**, confirm the four hardening postures are wired *in* rather than bolted on, and rehearse an **agent-version rollback** as a thing distinct from a code rollback.

This is a **worksheet**: prompts, fill-in cells, and a few *runnable gates* where a check can actually fire. It runs **fully offline** in `MOCK=1` — the rollout/shadow simulations and the checklist are all local; the live gates ride on `capstone/`'s own CI and `docker compose` smoke test (opt-in, ⚠️ flagged). *Build yours first from the 🔧 Build sections, then use this pass to check it.*
""")

# 2. Why this matters ---------------------------------------------------------
md(r"""
## 🧠 Why this matters

A system that *works* is not a system that is *ready*. Hardening is not a pile of add-ons; it is **one posture** — *assume failure, measure quality, bound the blast radius* (§44.3). Every mechanism is an instance of it: breakers assume the provider fails, evals assume your own changes regress, guardrails assume hostile input, caps assume runaway spend, kill switches assume you will be wrong in ways you cannot yet name. Systems built this way fail *small, visibly, and recoverably* — and that property, not the absence of failure, is what "production-grade" means.

There is also a discipline the rest of the book only implied: how you **ship a change to the agent itself** (§44.2). When you push code, the regression you fear is a *500* — loud, alarmed-on. When you push an *agent*, the regression you fear is a **silent quality drop**: nothing throws, error rate stays flat, users just get worse answers and you find out from a satisfaction dip weeks later. The deployment machinery has to be built around *that* failure mode. This worksheet makes both concrete — and ends with the §44.5 checklist that turns the whole book into one operational artifact.
""")

# 3. Objectives + prereqs -----------------------------------------------------
md(r"""
## Objectives & prereqs

**By the end you can:**
- Pin a **prompt + tool + model triple** as one versioned artifact and explain why *it*, not the prompt file, is the unit of rollout (§44.2).
- Run a **canary on quality**, not just errors, and see why a 500-only canary is blind to an agent regression.
- Use **shadow mode** to bank agreement-rate before exposing a new agent (§44.2, Ch 43).
- Tell the **two rollback levers** apart — code rollback vs agent-version rollback — and rehearse the second.
- Run the **§44.5 master production-readiness checklist** against any agentic system, with hardening wired in *while* building (§44.3).

**Prereqs:** [`44-01-capstone-tour-one-request.ipynb`](44-01-capstone-tour-one-request.ipynb). Behind it: Ch 22–23 (evals + observability), Ch 28 (flags/canary), Ch 39–41 (gateway, cost, security), Ch 43 (autonomy dial / shadow mode).

**Packages:** Python standard library only (`os`, `random`, `statistics`). Offline and free in `MOCK=1`. The live gates (real eval suite, real cap) run on `capstone/`'s CI and `docker compose` — opt-in, ⚠️ flagged.
""")

# 4. Setup --------------------------------------------------------------------
code(r'''
# Setup — imports, env, the MOCK switch, and a fixed seed.
import os
import random
import statistics

from dotenv import load_dotenv

load_dotenv()  # reads a local .env if present; never hardcode keys

# MOCK=1 (default): the rollout/shadow simulations and checklist run locally on
# canned numbers — offline, free, deterministic. MOCK=0 would wire these gates to
# the live capstone (its CI eval suite and gateway caps) — opt-in, costs tokens.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

# Seed everything stochastic so the canary/shadow simulations are identical in CI.
SEED = 44
random.seed(SEED)

print(f"MOCK mode: {MOCK}  (offline worksheet — simulations are canned, no key required)")
''')

# 5. Agent-as-artifact: the triple --------------------------------------------
md(r"""
## The agent is an artifact: the prompt + tool + model triple (§44.2)

Agent behavior is the **joint product** of three things: the prompt, the tool definitions, and the model. You cannot reason about a change — or reproduce a complaint, or trust an eval result — if any one of them floats independently. So you pin all three together as **one versioned artifact**, deploy it as a unit, and record which version served every run (Chapter 23).
""")

code(r'''
# An agent version is a pinned triple, not a loose prompt file. This is the unit
# of rollout AND rollback (§44.2). Note the model is a PINNED id, never an alias.
AGENT_VERSIONS = {
    "v7": {
        "prompt_sha": "a1b2c3",
        "tools_sha": "9f8e7d",            # the tool schemas the agent may call
        "model": "claude-opus-4-5-20251101",  # pinned snapshot, NOT a moving alias
        "online_eval": 0.91,              # last measured online quality score
        "cost_per_task": 0.041,           # USD
    },
    "v8": {                                # the candidate we want to roll out
        "prompt_sha": "a1b2c4",            # one-line prompt tweak
        "tools_sha": "9f8e7d",
        "model": "claude-opus-4-5-20251101",
        "online_eval": None,               # unknown until we canary it
        "cost_per_task": None,
    },
}

incumbent, candidate = "v7", "v8"
print("pinned agent versions (the rollout/rollback unit):")
for ver, a in AGENT_VERSIONS.items():
    print(f"  {ver}: prompt={a['prompt_sha']} tools={a['tools_sha']} model={a['model']}")
''')

# 6. Predict moment -----------------------------------------------------------
md(r"""
## 🔮 Predict: a provider repoints a model alias underneath you

Suppose you had pinned the model as a **moving alias** (e.g. `claude-opus-latest`) instead of a dated snapshot, and overnight the provider repoints that alias to a new model. Your prompt file did not change. Your tools did not change. You shipped nothing.

**Predict** before running the next cell: does your agent's *behavior* change? Has your *version number* changed? And which of the three — prompt, tools, model — moved without your consent?
""")

code(r'''
# Show why the TRIPLE is the unit: a silent alias repoint is a behavior change you
# did not make and cannot explain — unless the model is pinned inside the artifact.
def behavior_changed(before: dict, after: dict) -> bool:
    keys = ("prompt_sha", "tools_sha", "model")
    return any(before[k] != after[k] for k in keys)


pinned_before = dict(AGENT_VERSIONS["v7"])
# Case A: you pinned a dated snapshot. The provider's alias churn cannot touch you.
pinned_after = dict(pinned_before)  # nothing moved
print("Pinned to a dated snapshot:")
print(f"  behavior changed? {behavior_changed(pinned_before, pinned_after)}  (version still v7)")

# Case B: you pinned a moving alias. Overnight it repoints to a different model.
alias_before = dict(pinned_before, model="claude-opus-latest")
alias_after = dict(alias_before, model="claude-opus-latest")  # same string...
alias_after["_resolves_to"] = "a-different-model-than-yesterday"  # ...different model
print("\nPinned to a moving alias:")
print(f"  string unchanged, but it now resolves to: {alias_after['_resolves_to']}")
print("  behavior changed? True  (version number says v7 — and it is LYING)")
''')

md(r"""
**What you just saw.** With a **dated snapshot**, alias churn cannot reach you: same triple, same behavior, same version. With a **moving alias**, the string in your config is identical while the model underneath is different — a behavior change you did not make, did not version, and cannot explain. That is why §44.2 insists the *triple* (with a pinned model id), not the prompt file, is the unit of rollout. Pin the snapshot; let the alias be someone else's problem.
""")

# 7. Rollout simulation: canary on quality ------------------------------------
md(r"""
## Canary on quality, not just errors (§44.2)

The eval gate (Chapter 22) is the offline filter — a new triple is not a candidate until it clears the golden sets. Then you roll out *the behavior change* progressively with the same flag/canary machinery from Chapter 28, but **watching different needles**: online eval score, user feedback, and cost per task (Chapters 22–23) — not just error rate and latency.

A canary that only watches 500s is **blind** to the exact regression agents produce. Below, the candidate `v8` has a *flat error rate* but a *quality drop*. Predict which canary catches it.
""")

code(r'''
# Simulate a 5% canary. v8 has the SAME error rate as v7 but a LOWER online eval
# score (a subtle quality regression). Two canaries watch: one on errors only, one
# on quality. Seeded, so the numbers are identical every run.
def simulate_canary(n=400, eval_mean=0.90, eval_drop=0.0, err_rate=0.008):
    scores, errors = [], 0
    for _ in range(n):
        if random.random() < err_rate:
            errors += 1
            continue
        scores.append(max(0.0, min(1.0, random.gauss(eval_mean - eval_drop, 0.05))))
    return {
        "n": n,
        "error_rate": errors / n,
        "mean_eval": statistics.mean(scores),
    }


control = simulate_canary(eval_mean=0.90, eval_drop=0.0)        # v7 incumbent
canary = simulate_canary(eval_mean=0.90, eval_drop=0.06)        # v8: quality drop, same errors

print(f"{'metric':<14}{'v7 (control)':>16}{'v8 (canary)':>16}{'delta':>12}")
print("-" * 58)
de = canary["error_rate"] - control["error_rate"]
dq = canary["mean_eval"] - control["mean_eval"]
print(f"{'error_rate':<14}{control['error_rate']:>16.3%}{canary['error_rate']:>16.3%}{de:>+12.3%}")
print(f"{'mean_eval':<14}{control['mean_eval']:>16.3f}{canary['mean_eval']:>16.3f}{dq:>+12.3f}")

# The two canary verdicts.
QUALITY_GATE = -0.02  # roll back if online eval drops more than 2 points
errors_canary_ok = abs(de) < 0.005
quality_canary_ok = dq > QUALITY_GATE
print(f"\n500-only canary verdict : {'PASS (blind to it)' if errors_canary_ok else 'FAIL'}")
print(f"quality canary verdict  : {'PASS' if quality_canary_ok else 'FAIL -> roll back v8'}")
''')

md(r"""
**What you just saw.** The error rates are indistinguishable, so the **500-only canary waves `v8` through** — straight into a quality regression that will reach 100% of traffic. The **quality canary** sees the online eval score drop past the gate and rolls back at 5%. This is the whole point of §44.2: agents fail *quietly*, so the canary has to watch the needle that moves quietly.
""")

# 8. Shadow mode --------------------------------------------------------------
md(r"""
## Shadow mode for high-risk changes (§44.2, Ch 43)

For a model swap on a sensitive surface, you do not even canary first — you run the new agent **alongside** the live one on real (or replayed) traffic, log what it *would* have done, and **serve the incumbent's output**. You bank agreement-rate and divergence data at production scale with **zero user exposure**. It is the Chapter 43 autonomy dial applied to a version bump.
""")

code(r'''
# Replay a slice of traffic through both agents; serve the incumbent, log the
# candidate's would-be output, and measure agreement. No user ever sees v8.
REPLAY = [
    "refund my last order",
    "summarize this week's feedback",
    "what's my current plan tier",
    "file a bug about slow search",
    "cancel my subscription",
    "escalate this to a human",
]


def incumbent_action(msg):  # v7, the served agent
    if "refund" in msg or "cancel" in msg:
        return "require_approval"
    if "summar" in msg or "tier" in msg:
        return "answer"
    return "create_ticket"


def candidate_action(msg):  # v8, shadow only — note one divergence on "cancel"
    if "refund" in msg:
        return "require_approval"
    if "cancel" in msg:
        return "auto_cancel"      # v8 would skip the approval — a RISKY divergence
    if "summar" in msg or "tier" in msg:
        return "answer"
    return "create_ticket"


agree = 0
print(f"{'request':<32}{'served (v7)':<18}{'shadow (v8)':<18}match")
print("-" * 76)
for msg in REPLAY:
    a, b = incumbent_action(msg), candidate_action(msg)
    match = a == b
    agree += match
    flag = "" if match else "  <-- divergence"
    print(f"{msg:<32}{a:<18}{b:<18}{str(match):<6}{flag}")
rate = agree / len(REPLAY)
print("-" * 76)
print(f"agreement rate: {rate:.0%}  ({agree}/{len(REPLAY)})  — users saw only v7")
print("divergence on 'cancel': v8 would skip an approval gate — block the rollout, investigate.")
''')

md(r"""
**What you just saw.** Shadow mode surfaced a **dangerous divergence** — `v8` would *auto-cancel* where `v7` requires approval — and it did so with **no user ever exposed** to it. Agreement-rate is the autonomy dial's evidence (Chapter 43): you do not promote `v8` until the divergences are understood and the risky ones are fixed. Shadow is how you learn a new agent's behavior at production scale *before* trusting it.
""")

# 9. Two rollback levers ------------------------------------------------------
md(r"""
## The two rollback levers (§44.2 senior lens)

Rollback for agents has **two distinct levers**, and confusing them costs you during an incident:

- **Code rollback** — revert the deploy, redeploy the previous image. Fixes a *crash* or a bad migration. Requires a build + deploy.
- **Agent-version rollback** — **repin** to the previous prompt + tool + model triple. Fixes a *quality regression*. It is **config-only, instant, no deploy**, because the triple is data, not a build.

The page at 2 a.m. is *"the new prompt is hallucinating refunds."* The remedy is to flip the pin back in seconds while the code stays exactly where it is. Build both levers, label them, and rehearse the agent rollback the same way you rehearse the deploy rollback — you will reach for it more often.
""")

code(r'''
# Make the two levers concrete and DISTINCT. Rehearse the agent-version rollback:
# it is a config flip with no deploy.
DEPLOYED_IMAGE = "capstone:2026.06.18"   # the running code (changed only by a deploy)
ACTIVE_AGENT = "v8"                      # the pinned triple (changed by a config flip)


def code_rollback(prev_image):
    # Requires a real redeploy: build + ship the previous image. Minutes, not seconds.
    return {"lever": "code", "action": f"redeploy {prev_image}", "needs_deploy": True}


def agent_version_rollback(prev_version):
    # Config-only: repin the triple. Instant. The code does not move.
    global ACTIVE_AGENT
    ACTIVE_AGENT = prev_version
    return {"lever": "agent-version", "action": f"repin triple -> {prev_version}",
            "needs_deploy": False}


print("Incident at 2 a.m.: 'the new agent is hallucinating refunds.'")
print(f"  before: image={DEPLOYED_IMAGE}  active_agent={ACTIVE_AGENT}")

fix = agent_version_rollback("v7")   # the RIGHT lever for a quality regression
print(f"  fix:    {fix['action']}  (needs deploy? {fix['needs_deploy']})")
print(f"  after:  image={DEPLOYED_IMAGE}  active_agent={ACTIVE_AGENT}  <-- code never moved")

print("\nWrong lever for this incident:")
wrong = code_rollback("capstone:2026.06.11")
print(f"  {wrong['action']}  (needs deploy? {wrong['needs_deploy']}) — slower, and it "
      "wouldn't even fix a quality drop the previous IMAGE also shipped.")
''')

md(r"""
**What you just saw.** The quality regression was fixed by **repinning the triple** — `active_agent` went `v8 → v7`, the deployed image **never moved**, and it took no deploy. Reaching for a code rollback here would be slower *and* might not even fix it (the bad prompt could ship in the previous image too). Two levers, two failure modes; label them in your runbook so nobody confuses them at 2 a.m.
""")

# 10. Hardening as runnable gates ---------------------------------------------
md(r"""
## Hardening as runnable gates (§44.3)

Where a check *can* fire, make it an **assertion**, not a vibe. Four gates below, one per hardening posture — each one fails loudly when the posture is missing. This is the difference between "we have evals" and "a dropped metric *blocks the merge*."
""")

code(r'''
# Four hardening postures as gates that actually fire. Each returns (ok, message).

# 1) Evals as a CI gate (Ch 22): a dropped gated metric blocks the merge.
def eval_gate(baseline: float, candidate: float, min_drop=-0.02):
    delta = candidate - baseline
    ok = delta >= min_drop
    return ok, f"faithfulness {baseline:.2f} -> {candidate:.2f} (delta {delta:+.2f})"

# 2) Observability (Ch 23): per-tenant token/cost accounting must EXIST in the trace.
def cost_accounting_gate(span: dict):
    required = {"tenant", "tokens", "cost_usd"}
    ok = required.issubset(span)
    return ok, f"trace span has fields {sorted(span)}"

# 3) Structural guardrail (Ch 41): tenant isolation in the DATA layer, not the prompt.
def isolation_gate(query: str, enforced_in: str):
    ok = "tenant_id" in query and enforced_in == "data_layer"
    return ok, f"isolation enforced_in={enforced_in}; query scopes tenant={'tenant_id' in query}"

# 4) Cost cap (Ch 39-40): budget trips at 50/80/100% with a per-feature kill switch.
def budget_cap_gate(spent: float, cap: float):
    pct = spent / cap
    tier = "OK"
    if pct >= 1.0:
        tier = "HARD CAP — kill switch armed"
    elif pct >= 0.8:
        tier = "ALARM 80%"
    elif pct >= 0.5:
        tier = "NOTICE 50%"
    ok = pct < 1.0
    return ok, f"spend {spent:.2f}/{cap:.2f} = {pct:.0%} -> {tier}"


checks = [
    ("eval gate (Ch 22)",        eval_gate(0.86, 0.84)),
    ("cost accounting (Ch 23)",  cost_accounting_gate({"tenant": "acme", "tokens": 1180, "cost_usd": 0.0028})),
    ("tenant isolation (Ch 41)", isolation_gate("SELECT * FROM docs WHERE tenant_id = %s", "data_layer")),
    ("budget cap (Ch 39-40)",    budget_cap_gate(spent=92.0, cap=100.0)),
]
for name, (ok, msg) in checks:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:<26} {msg}")
''')

md(r"""
**What you just saw.** Three gates pass and **one fails on purpose**: the `eval gate` sees faithfulness drop `0.86 → 0.84` (a 2-point regression) and **blocks the merge** — exactly what a CI gate is for. The cost-accounting gate confirms the trace carries per-tenant token/cost fields; isolation is enforced in the *data layer* (a `WHERE tenant_id` clause), not asked for in a prompt; and the budget cap reads `92%` and arms the 80% alarm. These are the four §44.3 postures as code that *fails* when the posture is absent.
""")

# 11. Pitfall -----------------------------------------------------------------
md(r"""
## ⚠️ Pitfall: hardening *sequentially*

The most common capstone-stage mistake is hardening *in order* — "ship first, add evals and guardrails next sprint" (§44.3). Next sprint never comes; traffic does. Retrofitting **observability** means debugging incidents blind. Retrofitting **evals** means changes already shipped unmeasured. Retrofitting **guardrails** means the injection already happened. Part VI sat *early* in this book for exactly this reason: the quality scaffolding goes in *while* you build, when it costs hours — not after launch, when it costs incidents.

The pass below enforces that: it checks that each posture is **already wired in**, and a missing one is a *blocker*, not a backlog ticket.
""")

code(r'''
# Enforce in-build hardening: every posture must already be wired. A missing one
# is a launch BLOCKER, not a "next sprint" item.
wired = {
    "evals_in_ci": True,
    "tracing_per_tenant": True,
    "structural_guardrails": True,
    "budget_caps_and_kill_switch": True,
}
blockers = [k for k, v in wired.items() if not v]
if blockers:
    print(f"LAUNCH BLOCKED — hardening not wired: {blockers}")
else:
    print("All four hardening postures wired IN (not bolted on). Cleared to proceed.")
print("Rule (§44.3): a missing posture is a blocker today, never a backlog item for 'next sprint'.")
''')

# 12. The master checklist ----------------------------------------------------
md(r"""
## 📋 The full production-readiness checklist (§44.5)

The book's master operational artifact — seven sections, each line compressing a chapter. Run it before any launch, the capstone's or your own. Mark each box **owned / checked / flagged** against `capstone/` (or your system), and keep the chapter reference so you can jump back to the detail.

This lifts directly into [`../../../templates/production-readiness-checklist/`](../../../templates/production-readiness-checklist/) (Appendix F).

### Architecture & design
- [ ] Requirements written and *ranked*, with the three AI NFRs — quality, cost/task, safety posture — pinned numerically (Ch 42)
- [ ] Estimation done: tokens, \$/day, peak call rate vs provider quotas, storage (Ch 42)
- [ ] Simplest architecture that meets the ranked NFRs; alternatives recorded (Ch 27)
- [ ] Boundaries around business capabilities; modules independently testable (Ch 27–28)
- [ ] Expensive decisions captured as ADRs with rejected options and revisit triggers (Ch 27)

### Reliability & scale
- [ ] Every external call has a timeout; whole-run deadlines propagate (Ch 29, 42)
- [ ] Retries: backoff + jitter, capped, idempotent operations only; idempotency keys on all side-effecting tools (Ch 29)
- [ ] Circuit breakers per provider/tool; fallback ladder defined and product-approved (Ch 42)
- [ ] API tier stateless; long runs in workers with checkpoints; resume tested (Ch 14, 31)
- [ ] Queues bounded; back-pressure and shedding rules; autoscaling on queue depth (Ch 31, 42)
- [ ] Multi-AZ; health checks and graceful shutdown; load-tested at 2× estimated peak (Ch 28, 33)

### Data
- [ ] Postgres modeled, indexed, migrated; connection pooling sized (Ch 30)
- [ ] Freshness SLO stated; ingestion idempotent and re-runnable; rebuild-from-source safe (Ch 42)
- [ ] Backups automated *and restore tested*; retention and tiering for traces (Ch 30)
- [ ] Caches scoped per tenant; invalidation rules written down (Ch 30, 40)

### Security & safety
- [ ] OWASP LLM Top 10 reviewed; injection defenses on retrieved and tool-returned content (Ch 41)
- [ ] Least-privilege everywhere: IAM roles per service, scoped tool permissions, no long-lived keys (Ch 33, 41)
- [ ] Tenant isolation enforced in the data layer, not in prompts; permission probes in the eval suite (Ch 41, 43)
- [ ] Irreversible actions human-gated; agent sandboxes bounded; secrets in a manager, never in code (Ch 20, 28, 41)
- [ ] PII handling, data residency, and compliance posture documented (Ch 41)

### Quality: evals & observability
- [ ] Golden sets for RAG and agent trajectories; eval harness gates CI merges (Ch 22)
- [ ] Online sampling with LLM-as-judge; drift alarms on quality scores (Ch 22)
- [ ] Full tracing: spans per model/tool call; token and cost accounting per tenant (Ch 23)
- [ ] Dashboards: up / fast / good / cost; alerts on SLO burn and spend rate, not noise (Ch 23)
- [ ] Feedback-to-eval harvest path working: bad traces become eval cases weekly (Ch 21–22)

### Cost
- [ ] Budgets per run, tenant, and day enforced at the gateway; hard caps tested (Ch 39–40)
- [ ] Model routing by difficulty; prompt and response caching measured (Ch 39–40)
- [ ] Billing alarms at 50/80/100%; cost per task tracked against the estimate (Ch 32, 42)

### Operations & launch
- [ ] Infra as code; CI/CD deploys reproducibly; rollback rehearsed, one command (Ch 36)
- [ ] Runbooks for the top failure modes; kill switch per feature (Ch 23)
- [ ] Game day run: provider brownout, worker death, queue flood — ladder held (Ch 42)
- [ ] Feature flags + canary + progressive rollout wired; shadow mode for risky autonomy (Ch 28, 43)
- [ ] Agent behavior pinned as a versioned prompt + tool + model triple; version recorded per run; canary watches eval scores and cost, not just errors (Ch 22–23, 44)
- [ ] Agent-version rollback (repin the triple) separate from code rollback, config-only and rehearsed (Ch 44)
- [ ] On-call rotation, postmortem process, and the weekly quality review scheduled (Ch 23)
""")

# 13. Runnable checklist scorer -----------------------------------------------
md(r"""
### ✍️ Score your system against the seven sections

Fill in your honest counts per section (owned/checked vs total), then run the cell to see your readiness at a glance. *Owned* means a named person; *checked* means verified against the running system, not assumed.
""")

code(r'''
# Tally the §44.5 checklist. Replace `checked` with YOUR honest count per section
# after walking each box against capstone/ (or your system).
SECTIONS = [
    # (section,                         total_boxes, checked_so_far)
    ("Architecture & design",            5, 5),
    ("Reliability & scale",              6, 6),
    ("Data",                             4, 3),
    ("Security & safety",                5, 4),
    ("Quality: evals & observability",   5, 5),
    ("Cost",                             3, 3),
    ("Operations & launch",              7, 6),
]

total = sum(t for _, t, _ in SECTIONS)
done = sum(c for _, _, c in SECTIONS)
print(f"{'section':<34}{'done/total':>12}  status")
print("-" * 64)
for name, t, c in SECTIONS:
    status = "READY" if c == t else f"{t - c} open"
    bar = "#" * round((c / t) * 12)
    print(f"{name:<34}{f'{c}/{t}':>12}  {bar:<12} {status}")
print("-" * 64)
print(f"{'TOTAL':<34}{f'{done}/{total}':>12}  overall {done/total:.0%}")
if done < total:
    print(f"\nNot launch-ready: {total - done} box(es) open. Every box needs an owner before ship.")
else:
    print("\nEvery box checked — readiness confirmed.")
''')

md(r"""
**What you just saw.** The checklist is not a feeling; it is a **score with owners**. Two boxes open here (one in Data, one in Operations) means *not launch-ready* — each open box gets a name and a date before ship, or a deliberate, documented waiver. A green checklist is the moment the whole book becomes a single operational artifact behind your system.
""")

# 14. Senior lens -------------------------------------------------------------
md(r"""
## 🎯 Senior lens

After launch, the scarce resource is **trust in the iteration loop** (§44.4). Teams that bypass it — *"just tweak the prompt in prod, it's only words"* — accumulate unmeasured changes until nobody knows why quality moved, and then *every* change is feared and the team slows to a crawl. Teams that keep prompts, configs, and model choices **versioned, gated, and canaried** move *faster* within a year, because every change carries evidence.

So your job as the architect is to **make the disciplined path the easy path**: the harness in CI, the flags in place, the dashboards one click away, the agent-rollback a single config flip. Process you have to *remember* is process that erodes; the senior move is building it into the rails so the right thing is also the convenient thing. That is what every gate in this worksheet is really for.
""")

# 15. Recap -------------------------------------------------------------------
md(r"""
## Recap

- The agent is an **artifact**: pin the **prompt + tool + model triple** (with a dated model snapshot) and record the version per run — *that*, not the prompt file, is the rollout/rollback unit (§44.2).
- **Canary on quality**, not just errors: a 500-only canary is blind to the silent quality drop agents produce.
- **Shadow mode** banks agreement-rate with zero user exposure before you trust a new agent (Ch 43).
- **Two rollback levers**: code rollback (redeploy, needs a build) vs agent-version rollback (repin the triple, config-only, instant) — label and rehearse both (§44.2).
- Hardening is **one posture** — *assume failure, measure quality, bound the blast radius* — wired **in while building**, then verified by the **§44.5 master checklist** with every box owned (§44.3, §44.5).
""")

# 16. Exercises ---------------------------------------------------------------
md(r"""
## Exercises

1. **Tune the quality gate.** Change `QUALITY_GATE` in the canary cell to `-0.10`. Predict whether `v8` now passes, and argue what business context would justify a looser gate (and what it costs you).
2. **A second divergence.** Add a request to `REPLAY` where `v8` is *better* than `v7` (e.g. it escalates a case `v7` mishandles). Predict the new agreement rate. Does a lower agreement rate always mean "do not ship"? Explain.
3. **Trip the hard cap.** Call `budget_cap_gate(spent=100.0, cap=100.0)` and `budget_cap_gate(spent=101.0, cap=100.0)`. Predict each verdict and confirm the kill switch arms at 100%, not 80%.
4. **Close your two boxes.** Take the two open boxes in the scorer (Data, Operations). Write the concrete artifact each one needs (e.g. a tested restore script; a rehearsed agent-rollback runbook entry), name an owner, and set `checked` to full.
""")

code("# Exercise scratch space — your code here.\n")
code("# Exercise scratch space — your code here (or keep it prose; this is a worksheet).\n")

# 17. Next --------------------------------------------------------------------
md(r"""
## Next

- **Run it for real (opt-in, ⚠️):** the live gates ride on the capstone's own CI and smoke test. From the repo root: `cd capstone && docker compose up` brings up the stack, and the eval suite in [`../../../capstone/evals/`](../../../capstone/evals/) plus the gateway caps enforce these checks against real traffic. This is opt-in because it spends real tokens.
- **Diff against known-good:** compare your readiness pass to the reference [`../../../capstone/checkpoints/`](../../../capstone/checkpoints/) — *build yours first, then compare.*
- **Templates:** your filled checklist lifts into [`../../../templates/production-readiness-checklist/`](../../../templates/production-readiness-checklist/) (Appendix F); the thin-intake API it assumes is [`../../../templates/fastapi-agent-service/`](../../../templates/fastapi-agent-service/).
- **Book:** keep §44.5 open whenever you ship — the capstone's or your own. This worksheet is its runnable companion, and the close of the book: *the code, increasingly, the machines will write. This — requirements ranked, trade-offs explicit, failure assumed, blast radius bounded — is the part that stays yours.*
""")

# Assemble & write ------------------------------------------------------------
nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = "44-02-production-readiness-pass.ipynb"
with open(out, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
    f.write("\n")
print(f"wrote {out} with {len(cells)} cells")
