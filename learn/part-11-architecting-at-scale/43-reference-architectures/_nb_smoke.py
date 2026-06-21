# Setup --- imports, env, and the MOCK switch.
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
print("No API key required. Nothing leaves this machine.")

# ---- next code cell ----
# The four reference architectures as data --- the §43.5 table, verbatim.
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
    print(f"{a.name:<34} -> {a.hardest_problem}")

# ---- next code cell ----
# A tiny router: rank your requirements, get the architecture (pure lookup, offline).
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
        ["cost per item", "throughput", "measurable quality", "resumability"])

# ---- next code cell ----
# Same scenario, ONE requirement re-ranked to the top. Predict the new box first.
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
print(f"                 -> {after.top_risk}")

# ---- next code cell ----
# Autonomy dial: promote an action to autonomous only when measured agreement
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
    print(f"{s.action:<24}{s.threshold:>10.2%}{obs:>10.2%}  {autonomy_verdict(s, obs)}")

# ---- next code cell ----
# ADR-044 back-of-envelope: why latency x unit-cost FORCES tiered routing.
# Pure arithmetic, no model call. Numbers chosen to reproduce the chapter's figures.

# --- usage assumptions (Ch 42 estimator inputs) ---
turns_per_user_per_month = 100        # modest engagement for a consumer copilot
frontier_cost_per_turn = 0.0055       # blended $/turn on the frontier model
small_cost_per_turn = 0.00055         # ~1/10th the price on the small model
plan_price_per_month = 12.00          # the subscription this must fit inside
small_model_match_rate = 0.78         # evals: small model matches frontier on 78% of turns

# The margin reality (the part juniors skip): the $12 plan does NOT all go to
# inference. Support, infra, payments, R&D, sales, and profit eat most of it. A
# healthy SaaS leaves only a thin slice -- call it 5% of revenue -- for model spend.
inference_budget_fraction = 0.05
inference_budget = plan_price_per_month * inference_budget_fraction  # $0.60/user/mo

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
print("inference alone, leaving nothing for the long tail of expensive turns or growth.")

# ---- next code cell ----
# Two retrievers over the same corpus. One filters by ACL; one does not.
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
print("the model literally never sees comp-2026 -- it cannot summarize what it never received.")

# ---- next code cell ----
# Exercise scratch space --- your code here.


# ---- next code cell ----
# Exercise scratch space --- your code here.
