"""Temporary builder for 43-01-requirement-driven-architecture.ipynb.

Constructs a valid nbformat-4 notebook with cleared outputs and null execution_count.
Run from this folder; it writes the .ipynb next to itself. This file is deleted after.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "43-01-requirement-driven-architecture.ipynb")


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(text)}


def code(text):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _lines(text),
    }


def _lines(text):
    # Preserve a trailing newline on every line except the last, matching nbformat.
    lines = text.split("\n")
    out = []
    for i, line in enumerate(lines):
        if i < len(lines) - 1:
            out.append(line + "\n")
        else:
            if line != "":
                out.append(line)
    return out


cells = []

# 1. Title + header --------------------------------------------------------------
cells.append(md(
"""# Which requirement forced which box

> 📓 *Companion to* **Modern Agentic AI Engineer** · Ch 43 §43.1–43.5 · type: concept-lab

**The promise:** by the end you can take a *ranked requirement profile*, run a tiny router over the four reference architectures, and have it tell you which shape fits, what its **hardest problem** is, its **signature pattern**, its **top risk** — and the blueprint that implements it. Then you can defend that choice the way Chapter 43 does: *requirement first, box second.*

This notebook is fully offline and free: no API key, no services, nothing to install beyond the standard library. Every "decision" is a deterministic lookup over the chapter's own comparison table — which is the point. The chapter's lesson is not a model; it is a discipline."""
))

# 2. Why this matters ------------------------------------------------------------
cells.append(md(
"""## 🧠 Why this matters

Chapter 42 gave you the *method* for system design; Chapter 43 gives you the *answers* other teams already paid for. Four architectures cover the overwhelming majority of agentic systems built today: the **enterprise RAG assistant**, the **autonomous workflow / ops agent**, the **customer-facing copilot**, and the **batch processing pipeline**. The temptation is to memorize the four boxes and copy whichever looks closest. That is exactly how teams end up running a durable workflow engine for a chatbot, or a streaming index for a nightly data job.

The real lesson lives one level down: **the ranked requirements, not the technology, chose every box.** *Permissions* made the RAG assistant. *Durability and audit* made the ops agent. *Latency × unit economics* made the copilot. *Cost per item* made the batch pipeline. Change the top requirement and a different architecture — with a different hardest problem and a different signature pattern — falls out.

This notebook makes that mechanical so you can feel it. We encode the chapter's four-row comparison table (§43.5) as data, build a small router that maps a requirement profile to an architecture, then *change a requirement and watch the box change*. When you can name which requirement forced each expensive box — and spot a box that no requirement forced (that box is fashion) — you are reasoning like the chapter wants you to."""
))

# 3. Objectives + prereqs --------------------------------------------------------
cells.append(md(
"""## Objectives & prereqs

**By the end you can:**
- Reproduce the §43.5 comparison table as a small data structure (architecture → hardest problem, signature pattern, top risk, blueprint).
- Run a **router** that, given a ranked requirement profile, returns the matching architecture and its signature pattern — and predict its answer before it speaks.
- Apply the **autonomy dial** (§43.2): promote an action to autonomous only when measured agreement clears your threshold.
- Reproduce the **ADR-044** cost logic (§43.3): why frontier-only ≈ \\$0.55/user/month against a \\$12 plan *forces* tiered routing.
- Jump from "which shape?" straight to the blueprint that implements it.

**Prereqs:** Chapter 43 read alongside. Chapter 42 (the method these are answers to — run its estimator first). Helpful background: Ch 13 (RAG), Ch 31 / 33 (durable workflows), Ch 39–40 (gateway / caching), Ch 15 (structured outputs).

**Packages:** standard library only. No external dependencies, no API key, no network. Every result is a deterministic lookup or arithmetic, so the notebook produces identical output in CI and for any reader."""
))

# 4. Setup -----------------------------------------------------------------------
cells.append(code(
'''# Setup --- imports, env, and the MOCK switch.
import os
import random
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # reads a local .env if present; never hardcode keys

# MOCK=1 (default) keeps everything offline, free, and deterministic. This notebook
# is mock-only by design: there is no live model call anywhere in it -- the chapter's
# lesson is table-driven reasoning, not generation. The switch is here so the pattern
# is identical to every other notebook in the repo.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

# Seed everything stochastic so the autonomy-dial simulation is identical every run.
SEED = 43
random.seed(SEED)

print(f"MOCK mode: {MOCK}  (offline, free, deterministic)")
print("No API key required. Nothing leaves this machine.")'''
))

# 5a. The comparison table (markdown) -------------------------------------------
cells.append(md(
"""## 🧠 The four architectures, compressed (§43.5)

Here is the chapter's comparison table — the whole of §43 in four rows. Each *signature pattern* exists **because of** the *hardest problem*: requirement first, box second.

| Architecture | Hardest problem | Signature pattern | Top risk |
|---|---|---|---|
| Enterprise RAG | Permissions | ACL-filtered retrieval + citations | Index / ACL drift; quiet quality decay |
| Workflow / ops agents | Durability + audit | Durable workflow engine; autonomy dial | Silent drift; runaway loops |
| Copilot at scale | Latency × unit cost | Tiered routing gateway + caching | Margin erosion; public abuse |
| Batch pipelines | Cost per item | Manifest + batch APIs + sampling QA | Schema evolution; shipped errors |

We encode this table as data so the router below can *reason over it* instead of us hand-waving. The `blueprint` field is the payload: each row points hard at the blueprint that realizes it, so this chapter is the index from "which shape?" to "study and lift the real one.\""""
))

# 5b. Encode the table (code) ----------------------------------------------------
cells.append(code(
'''# The four reference architectures as data --- the §43.5 table, verbatim.
@dataclass(frozen=True)
class Architecture:
    key: str                 # short id
    name: str                # display name
    hardest_problem: str     # the requirement that forced this box to exist
    signature_pattern: str   # the load-bearing pattern of this architecture
    top_risk: str            # the failure mode that kills it
    blueprint: str           # relative path to the blueprint that implements it


ARCHITECTURES = {
    "enterprise_rag": Architecture(
        key="enterprise_rag",
        name="Enterprise RAG assistant",
        hardest_problem="Permissions",
        signature_pattern="ACL-filtered retrieval + citations",
        top_risk="Index / ACL drift; quiet quality decay",
        blueprint="../../../blueprints/rag-pipeline/",
    ),
    "workflow_ops": Architecture(
        key="workflow_ops",
        name="Autonomous workflow / ops agent",
        hardest_problem="Durability + audit",
        signature_pattern="Durable workflow engine; autonomy dial",
        top_risk="Silent drift; runaway loops",
        blueprint="../../../blueprints/multi-agent-supervisor/",
    ),
    "copilot": Architecture(
        key="copilot",
        name="Customer-facing copilot at scale",
        hardest_problem="Latency x unit cost",
        signature_pattern="Tiered routing gateway + caching",
        top_risk="Margin erosion; public abuse",
        blueprint="../../../blueprints/observability-stack/",
    ),
    "batch": Architecture(
        key="batch",
        name="Batch / agentic data pipeline",
        hardest_problem="Cost per item",
        signature_pattern="Manifest + batch APIs + sampling QA",
        top_risk="Schema evolution; shipped errors",
        blueprint="../../../blueprints/eval-harness/",
    ),
}

for a in ARCHITECTURES.values():
    print(f"{a.name:<34} -> {a.hardest_problem}")'''
))

# 6a. Requirement -> shape mapping (markdown) -----------------------------------
cells.append(md(
"""## From requirement to shape, one architecture at a time

Each architecture is the answer to a *different* top-ranked requirement. The chapter walks them in order; here is the mapping in one place, stated as "the requirement that made the box":

- **Permissions** made the RAG assistant: ACL-filtered retrieval *before any text reaches the model*, plus citations as the trust mechanism (§43.1).
- **Durability + audit** made the ops agent: a durable workflow engine so a three-hour run survives a deploy, plus an autonomy *dial* you turn up as evals earn it (§43.2).
- **Latency × unit-cost** made the copilot: a tiered routing gateway (small model for the easy 80%, escalate on signal) plus aggressive caching, because a million users on a frontier model is a seven-figure bill (§43.3).
- **Cost-per-item** made the batch pipeline: a per-item manifest, batch APIs (~half price), spot compute, and sampling QA against a golden set (§43.4).

Now we build the router that turns a *ranked requirement profile* into exactly this mapping — no human in the loop, just the table."""
))

# 6b. The router function (code) ------------------------------------------------
cells.append(code(
'''# A tiny router: rank your requirements, get the architecture (pure lookup, offline).
#
# The chapter's claim is that the SINGLE top-ranked requirement decides the shape.
# So the router is deliberately simple: it reads requirement[0] and maps it. We keep
# a synonym table so a profile can speak in plain words ("permissions", "audit",
# "cost per item") and still resolve. No model, no magic -- this is the §43.5 logic.

REQUIREMENT_TO_ARCH = {
    # permissions / access-control family -> enterprise RAG
    "permissions": "enterprise_rag",
    "access control": "enterprise_rag",
    "data isolation": "enterprise_rag",
    # durability / audit family -> workflow / ops agent
    "durability": "workflow_ops",
    "auditability": "workflow_ops",
    "correctness and audit": "workflow_ops",
    "long-running": "workflow_ops",
    # latency x unit-cost family -> copilot
    "latency": "copilot",
    "unit economics": "copilot",
    "cost per user": "copilot",
    "abuse and safety": "copilot",
    # cost-per-item / throughput family -> batch
    "cost per item": "batch",
    "throughput": "batch",
    "resumability": "batch",
}


def route(ranked_requirements: list[str]) -> Architecture:
    """Map a ranked requirement profile to a reference architecture.

    Only the TOP requirement is load-bearing -- that is the chapter's whole point.
    Raises if the top requirement is unknown, so a 'fashion' choice cannot sneak in
    unnamed: every box must trace to a requirement.
    """
    if not ranked_requirements:
        raise ValueError("empty requirement profile: no requirement, no box.")
    top = ranked_requirements[0].strip().lower()
    if top not in REQUIREMENT_TO_ARCH:
        raise ValueError(
            f"unknown top requirement {top!r}. Name the requirement before the box "
            f"-- an unnamed box is fashion (§43.5)."
        )
    return ARCHITECTURES[REQUIREMENT_TO_ARCH[top]]


def explain(profile_name: str, ranked: list[str]) -> None:
    """Run the router and print the architecture + why it fell out + its blueprint."""
    arch = route(ranked)
    print(f"profile: {profile_name}")
    print(f"  ranked requirements : {ranked}")
    print(f"  -> architecture     : {arch.name}")
    print(f"     hardest problem  : {arch.hardest_problem}")
    print(f"     signature pattern: {arch.signature_pattern}")
    print(f"     top risk         : {arch.top_risk}")
    print(f"     blueprint        : {arch.blueprint}")
    print()


# The book's four canonical scenarios, as ranked requirement profiles.
explain("5k-person internal knowledge assistant",
        ["permissions", "trustworthiness", "freshness", "latency"])
explain("back-office invoice / ops agent",
        ["auditability", "durability", "throughput", "bounded autonomy"])
explain("consumer SaaS copilot (1M users)",
        ["latency", "unit economics", "abuse and safety", "multi-tenancy"])
explain("extract terms from 2M contracts",
        ["cost per item", "throughput", "measurable quality", "resumability"])'''
))

# 6c. what you just saw ----------------------------------------------------------
cells.append(md(
"""**What you just saw.** Four profiles, four different boxes — and you never named a technology, only a *requirement*. The router never looked at "we want a vector database" or "let's use Temporal"; it looked at what the system must *guarantee* and let the box follow. That inversion — guarantee first, component second — is the entire discipline of §43.5 compressed into a lookup."""
))

# 7. Predict moment --------------------------------------------------------------
cells.append(md(
"""## 🔮 Predict: flip the top requirement

Here is the lever. Take the **enterprise RAG assistant** profile — `["permissions", "trustworthiness", "freshness", "latency"]` — and imagine the business changes its mind: this is now a *bulk back-classification* job over 2 million historical documents, where the dominant constraint is **cost per item**, not who can see what. So we re-rank: `cost per item` moves to the front.

**Predict before you run the next cell:** which of the four architectures does the profile become? What is its new *hardest problem*, *signature pattern*, and *top risk*? Write your guess down — then run the cell and check."""
))

cells.append(code(
'''# Same scenario, ONE requirement re-ranked to the top. Predict the new box first.
original = ["permissions", "trustworthiness", "freshness", "latency"]
reranked = ["cost per item"] + original  # cost-per-item is now the binding constraint

before = route(original)
after = route(reranked)

print(f"top requirement: {original[0]!r:>16}  -> {before.name}")
print(f"top requirement: {reranked[0]!r:>16}  -> {after.name}")
print()
print("the box changed because the BINDING requirement changed:")
print(f"  hardest problem : {before.hardest_problem:<22} -> {after.hardest_problem}")
print(f"  signature       : {before.signature_pattern}")
print(f"                 -> {after.signature_pattern}")
print(f"  top risk        : {before.top_risk}")
print(f"                 -> {after.top_risk}")'''
))

cells.append(md(
"""**What you just saw.** Nothing about the *content* changed — same documents, same company. Re-ranking a single requirement flipped the entire architecture from an ACL-filtered, citation-bearing query path to a manifest-driven batch pipeline with sampling QA. This is why the chapter insists you rank requirements *before* you draw boxes: the ranking is the architecture. Reach for the box first and you will defend it forever, even after the requirement that justified it is gone."""
))

# 8. Autonomy dial ---------------------------------------------------------------
cells.append(md(
"""## 🎯 The autonomy dial (§43.2) — the chapter's most reusable pattern

The ops-agent section gives you the single most portable pattern in the chapter: **design autonomy as a dial, not a switch, and let evals move it.** Launch with the agent *proposing* and humans *approving* everything. Measure the agreement rate per action type. When the agent's proposals match human decisions at a threshold you trust *for that action*, promote that action to autonomous — and keep auditing samples.

Below we simulate per-action agreement rates over a window of decisions and apply the rule. This converts "should we trust the agent?" from a debate into a measured, reversible, per-action decision. Ch 44 reuses exactly this seed for its shadow-mode launch."""
))

cells.append(code(
'''# Autonomy dial: promote an action to autonomous only when measured agreement
# clears its threshold. Deterministic under SEED so the verdicts are reproducible.

@dataclass
class ActionStats:
    action: str
    threshold: float        # the agreement rate this action must clear to go autonomous
    true_agreement: float   # the (hidden) real agreement rate we are sampling from


def simulate_agreement(stats: ActionStats, n: int = 200) -> float:
    """Sample n agent-vs-human decisions; return the observed agreement rate."""
    hits = sum(1 for _ in range(n) if random.random() < stats.true_agreement)
    return hits / n


def autonomy_verdict(stats: ActionStats, observed: float) -> str:
    """The rule: promote to autonomous iff observed agreement >= the action's threshold."""
    if observed >= stats.threshold:
        return "PROMOTE -> autonomous (keep auditing samples)"
    return "HOLD -> human-in-the-loop (gather more evidence)"


# A realistic spread: a safe, frequent action clears easily; a money-touching one
# is held to a higher bar AND has not yet earned it.
actions = [
    ActionStats("tag_invoice_category", threshold=0.95, true_agreement=0.985),
    ActionStats("match_invoice_to_po",  threshold=0.97, true_agreement=0.974),
    ActionStats("auto_approve_payment", threshold=0.99, true_agreement=0.965),
    ActionStats("escalate_to_human",    threshold=0.90, true_agreement=0.992),
]

print(f"{'action':<24}{'threshold':>10}{'observed':>10}  verdict")
print("-" * 78)
for s in actions:
    obs = simulate_agreement(s)
    print(f"{s.action:<24}{s.threshold:>10.2%}{obs:>10.2%}  {autonomy_verdict(s, obs)}")'''
))

cells.append(md(
"""**What you just saw.** Autonomy is now a *measurement*, not a vote. The cheap, frequent action (`tag_invoice_category`) cleared its bar and goes autonomous; `auto_approve_payment` — the one that moves money — is held to a stricter 99% threshold *and* has not earned it, so it stays human-approved. Same agent, different verdict per action. That is the dial: reversible (drop an action back the moment agreement decays), auditable, and shippable without betting the company on a single switch."""
))

# 9. Cost-as-product / ADR-044 ---------------------------------------------------
cells.append(md(
"""## Cost is product: reproducing the ADR-044 logic (§43.3)

The copilot section's claim is concrete: *cost engineering is product engineering.* The worked example is **ADR-044** — tiered model routing — and its numbers are the reason the box exists. Reusing Chapter 42's back-of-envelope estimator:

- Frontier-model-only serving projects to **≈ \\$0.55 / user / month** at current usage — untenable against a **\\$12 / month** plan whose *inference budget* is only a thin slice of revenue (support, infra, R&D, and profit claim the rest).
- Offline evals show the **small model matches the frontier model on 78%** of real traffic turns.
- Routing the easy majority to the small model yields a **≈ 70% projected cost reduction**.

We reproduce that arithmetic below so you can see *why no requirement leaves room for "frontier-only": the model budget forbids it.* The trap is comparing \\$0.55 to the headline \\$12 and concluding "cheap" — the real comparison is against the slice of that \\$12 you are actually allowed to spend on inference."""
))

cells.append(code(
'''# ADR-044 back-of-envelope: why latency x unit-cost FORCES tiered routing.
# Pure arithmetic, no model call. Numbers chosen to reproduce the chapter's figures.

# --- usage assumptions (Ch 42 estimator inputs) ---
turns_per_user_per_month = 100        # modest engagement for a consumer copilot
frontier_cost_per_turn = 0.0055       # blended $/turn on the frontier model
small_cost_per_turn = 0.00055         # ~1/10th the price on the small model
plan_price_per_month = 12.00          # the subscription this must fit inside
small_model_match_rate = 0.78         # evals: small model matches frontier on 78% of turns

# The margin reality (the part juniors skip): the $12 plan does NOT all go to
# inference. Support, infra, payments, R&D, sales, and profit eat most of it. A
# healthy SaaS leaves only a thin slice -- here 3% of revenue -- for model spend.
inference_budget_fraction = 0.03
inference_budget = plan_price_per_month * inference_budget_fraction  # $0.36/user/mo

# --- frontier-only path ---
frontier_only = turns_per_user_per_month * frontier_cost_per_turn

# --- tiered path: 78% of turns served by the small model, 22% escalate to frontier ---
small_turns = turns_per_user_per_month * small_model_match_rate
frontier_turns = turns_per_user_per_month * (1 - small_model_match_rate)
tiered = small_turns * small_cost_per_turn + frontier_turns * frontier_cost_per_turn

reduction = 1 - tiered / frontier_only

print(f"frontier-only cost : ${frontier_only:>6.2f} / user / month")
print(f"tiered routing cost: ${tiered:>6.2f} / user / month")
print(f"projected reduction: {reduction:>6.0%}")
print()
print(f"plan price         : ${plan_price_per_month:>6.2f} / user / month")
print(f"inference budget   : ${inference_budget:>6.2f} / user / month "
      f"({inference_budget_fraction:.0%} of revenue -- the rest is support, infra, profit)")
print()
# The verdict is about the BUDGET, not the headline plan price. Frontier-only blows
# the inference budget; the tiered path fits inside it. That is what 'forces' the box.
frontier_fits = frontier_only <= inference_budget
tiered_fits = tiered <= inference_budget
print(f"frontier-only ${frontier_only:.2f}  vs budget ${inference_budget:.2f}  -> "
      f"{'fits' if frontier_fits else 'BLOWS the budget'}")
print(f"tiered       ${tiered:.2f}  vs budget ${inference_budget:.2f}  -> "
      f"{'fits' if tiered_fits else 'BLOWS the budget'}")
print()
verdict = "FORCED" if (not frontier_fits and tiered_fits) else "optional"
print(f"tiered routing is {verdict}: frontier-only eats the entire model budget on")
print("inference alone, leaving nothing for the long tail of expensive turns or growth.")'''
))

cells.append(md(
"""**What you just saw.** The ≈ \\$0.55 frontier-only figure and the ≈ 70% reduction are not opinions; they fall straight out of the usage assumptions and the 78% match rate. The estimator *makes the routing decision for you* — which is precisely why ADR-044 records the deltas (why small-first, why escalate-on-signal, what you rejected). The deltas are the ADR; the ADR is what turns a borrowed box into defensible judgment."""
))

# 10. Pitfall --------------------------------------------------------------------
cells.append(md(
"""## ⚠️ Pitfall: the enterprise-RAG breach pattern (§43.1)

The breach in enterprise RAG is always the same shape: the index is built with a **privileged service account**, retrieval **ignores document ACLs**, and the assistant cheerfully summarizes the executive-compensation file to anyone who asks nicely. The fatal misconception is thinking you can fix this *in the prompt* — telling the model "don't reveal restricted content." **The model cannot unsee what retrieval hands it**, and prompt instructions are not access control (Ch 41).

The fix is structural: **filter at retrieval, against the index's ACL metadata, before any text reaches the model.** Below, two retrieval functions over the same documents — the broken one and the fixed one — show the difference where it bites."""
))

cells.append(code(
'''# Two retrievers over the same corpus. One filters by ACL; one does not.
# This is the §43.1 lesson made literal -- and the reason it is the chapter's pitfall.

DOCS = [
    {"id": "wiki-101",  "acl": {"all-staff"},        "text": "How to request PTO."},
    {"id": "policy-22", "acl": {"all-staff"},        "text": "Expense policy summary."},
    {"id": "comp-2026", "acl": {"hr", "exec"},       "text": "Executive compensation table."},
    {"id": "legal-07",  "acl": {"legal", "exec"},    "text": "Pending litigation summary."},
]


def retrieve_unfiltered(query_terms: set[str], caller_groups: set[str]) -> list[dict]:
    """BROKEN: ranks by keyword, ignores ACLs. The privileged-index breach pattern."""
    # Caller groups are accepted but never consulted -- exactly the bug.
    return [d for d in DOCS if query_terms & set(d["text"].lower().split())]


def retrieve_acl_filtered(query_terms: set[str], caller_groups: set[str]) -> list[dict]:
    """FIXED: filter against ACL metadata BEFORE any text is returned to the model."""
    visible = [d for d in DOCS if d["acl"] & caller_groups]   # permission check FIRST
    return [d for d in visible if query_terms & set(d["text"].lower().split())]


# An ordinary employee (all-staff only) asks a question that also matches a secret doc.
caller = {"all-staff"}
query = {"compensation", "policy"}

broken = retrieve_unfiltered(query, caller)
fixed = retrieve_acl_filtered(query, caller)

print("caller groups:", caller)
print()
print("UNFILTERED retrieval hands the model:")
for d in broken:
    leak = "  <-- LEAK" if not (d["acl"] & caller) else ""
    print(f"  {d['id']:<10} acl={sorted(d['acl'])}{leak}")
print()
print("ACL-FILTERED retrieval hands the model:")
for d in fixed:
    print(f"  {d['id']:<10} acl={sorted(d['acl'])}")
print()
assert all(d["acl"] & caller for d in fixed), "ACL filter must never return invisible docs"
print("the model literally never sees comp-2026 -- it cannot summarize what it never received.")'''
))

cells.append(md(
"""**What you just saw.** The unfiltered retriever handed the executive-compensation row to an all-staff employee; the model would have summarized it faithfully, because that is its job. The ACL-filtered retriever removed the document *before generation*, so there is nothing to leak. Note where the check lives: in the **retrieval query**, not the prompt. Sync ACL changes on the same SLO as content, and add **permission probes** (queries that should return nothing) to the eval suite (§43.1)."""
))

# 11. Senior lens ----------------------------------------------------------------
cells.append(md(
"""## 🎯 Senior lens — borrowed boxes need recorded reasoning

Read the four architectures as one lesson: *the ranked requirements, not the technology, chose every shape* (§43.5). When someone proposes an architecture, ask which requirement forced each expensive box. If no requirement did, **the box is fashion** — and fashion is how teams end up running a workflow engine for a chatbot or a streaming index for nightly data.

The router you ran is the cheerful version of that interrogation; the serious version is the **ADR**. A reference architecture borrowed *without* recorded reasoning is cargo cult; the same architecture *with* ADRs for the deltas — why Temporal over Celery, why retrieval filters by ACL metadata instead of per-team indexes, why the router defaults to the small model — is judgment you can defend, revisit, and hand to the next engineer. **The deltas are your ADRs.** That habit, not the four boxes, is what Chapter 43 is actually teaching, and it is why this chapter ships with the [`adr-template`](../../../templates/adr-template/)."""
))

# 12. Recap ----------------------------------------------------------------------
cells.append(md(
"""## Recap

- The four reference architectures are answers to four *different* top-ranked requirements: **permissions** → RAG assistant, **durability + audit** → ops agent, **latency × unit cost** → copilot, **cost per item** → batch pipeline.
- A box you cannot trace back to a requirement is **fashion** — name the requirement first, draw the box second.
- The **autonomy dial** turns "should we trust the agent?" into a measured, reversible, per-action decision: promote only when agreement clears that action's threshold.
- **Cost is product:** the ADR-044 arithmetic (≈ \\$0.55/user/mo frontier-only, 78% small-model match, ≈ 70% reduction) *forces* tiered routing — the margin leaves no choice.
- Enforce permissions at **retrieval**, before any text reaches the model — the model cannot unsee what retrieval hands it.
- Borrowed architectures need recorded reasoning: **the deltas are your ADRs.**"""
))

# 13. Exercises ------------------------------------------------------------------
cells.append(md(
"""## Exercises

Each exercise *changes one requirement* and asks you to predict which box must change before you run it. Solutions go in `solutions/` (Phase 2), not inline.

1. **Give the ops agent a latency requirement.** Take the invoice-agent profile and move a hard *first-token latency* requirement to the top (it now drives an interactive approval UI). Predict which architecture it becomes and what its new top risk is, then route it. Was durability lost, or just demoted?
2. **A fifth requirement family.** Add a new requirement — say *regulatory residency* (data must stay in-region) — to `REQUIREMENT_TO_ARCH`. Decide which existing architecture it maps to (or argue it needs a new row). Defend the mapping in two sentences, the way an ADR would.
3. **Move the autonomy threshold.** In the dial simulation, raise `match_invoice_to_po`'s threshold to 0.98 and lower `auto_approve_payment`'s true agreement to 0.94. Predict which verdicts flip, then run it. Which action would you *demote* first if agreement decayed in production?
4. **Re-price the copilot.** In the ADR-044 cell, change the plan to \\$5/month and the small-model match rate to 0.60. Predict whether tiered routing still clears the margin, then compute it. At what match rate does frontier-only become viable again?
5. **Write the delta as an ADR.** Pick any one routing decision above and write it as a 6-line ADR using [`templates/adr-template/`](../../../templates/adr-template/): Status, Context, Decision, Consequences (+/−), Rejected. That delta *is* your architecture record."""
))

cells.append(code("# Exercise scratch space --- your code here.\n"))
cells.append(code("# Exercise scratch space --- your code here.\n"))

# 14. Next -----------------------------------------------------------------------
cells.append(md(
"""## Next

- **Study the real boxes.** This chapter is the index from "which shape?" to "lift the production version." Each architecture points at its blueprint:
  - Enterprise RAG → [`blueprints/rag-pipeline/`](../../../blueprints/rag-pipeline/) (ACL-aware retrieval, citations) with permission-probe / faithfulness evals in [`blueprints/eval-harness/`](../../../blueprints/eval-harness/).
  - Workflow / ops agent → [`blueprints/multi-agent-supervisor/`](../../../blueprints/multi-agent-supervisor/) plus the durable-run / idempotency seams of [`blueprints/agent-loop/`](../../../blueprints/agent-loop/).
  - Copilot at scale → the gateway / tiered-routing and cost layer in [`blueprints/observability-stack/`](../../../blueprints/observability-stack/).
  - Batch pipeline → the structured-output + sampling-QA patterns and golden-set sampling in [`blueprints/eval-harness/`](../../../blueprints/eval-harness/).
- **Record your deltas.** Use [`templates/adr-template/`](../../../templates/adr-template/) — the chapter's ADR-044 is the worked instance.
- **Run the method first.** If you skipped it, Chapter 42's estimator is the back-of-envelope this notebook reused: [`../42-system-design-for-ai/`](../42-system-design-for-ai/).
- **Next chapter:** Chapter 44 assembles one of these — the workflow / RAG hybrid — as the full capstone: [`../44-capstone-end-to-end/`](../44-capstone-end-to-end/), instantiated in [`../../../capstone/`](../../../capstone/)."""
))

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(notebook, f, indent=1, ensure_ascii=False)
    f.write("\n")

print(f"wrote {OUT} with {len(cells)} cells")
