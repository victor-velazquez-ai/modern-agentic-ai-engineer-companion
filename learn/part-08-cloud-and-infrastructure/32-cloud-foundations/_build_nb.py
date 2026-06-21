"""Temporary generator for 32-01-four-primitives-and-finops.ipynb.

Builds a valid nbformat-4 notebook with cleared outputs (execution_count=null,
outputs=[]). This helper is deleted right after it runs; it exists only so the
source-line splitting stays exact and shell quoting can't corrupt the content.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "32-01-four-primitives-and-finops.ipynb")


def _lines(text):
    text = text.strip("\n")
    parts = text.split("\n")
    if len(parts) == 1:
        return [parts[0]]
    return [p + "\n" for p in parts[:-1]] + [parts[-1]]


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


cells = []

# 1. Title + header
cells.append(md(r"""
# The four primitives, and the bill they generate

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 32 §32.1–§32.3 · type: concept-lab*

*One-line promise:* classify **any** cloud service on sight into compute / storage / network / identity, then cost a small agent stack — and catch the forgotten-resource trap — **with no cloud account and no spend.**
"""))

# 2. Why this matters
cells.append(md(r"""
## 🧠 Why this matters

A cloud console shows you 200+ services and dares you to feel behind. You aren't: every one of them is a flavor of just **four primitives** — *compute* (machines to run code), *storage* (places to keep data), *network* (wiring and isolation), and *identity* (who can do what). Memorizing services is hopeless; *classifying* them is a five-second habit you'll use for the rest of your career. The second half of the cloud is money: unlike a data center where capacity is a sunk cost, here **cost is a variable you control with architecture**, and it spirals quietly — a GPU left on over a weekend, egress nobody watched. This lab makes both ideas operational: you sort real AWS/Azure/GCP names onto the map, then run a tiny offline cost model that shows how *design*, not usage alone, drives the invoice.
"""))

# 3. Objectives + prereqs
cells.append(md(r"""
## Objectives & prereqs

**By the end you can:**
- Classify any unfamiliar service into **compute / storage / network / identity** (or spot a *combo* built from them).
- Read an architecture's bill as a sum of primitive line items, and tell which one dominates.
- Show that **on-demand vs spot vs reserved** is an architecture choice, not a usage one — and quantify the difference.
- Name where a bill quietly grows (idle/forgotten resources, egress) and how a day-one budget alarm catches it.
- Sort security concerns across the **shared-responsibility** line (provider's job vs. yours).

**Prereqs:** none for cloud. Ch 29–31 (distributed systems, the data layer, workers) make the example stack concrete — it reuses that capstone shape — but aren't strictly required.

**Cost:** `none — fully offline`. `MOCK=1` (the default) runs a pure-stdlib classifier and cost toy over two tiny committed fixtures. **No cloud account, no SDK, no spend, deterministic.** There is deliberately no live path here: this is the *map*, not the territory.
"""))

# 4. Setup
cells.append(code(r"""
import json
import os
import random
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads a git-ignored .env if present; we never hardcode or need a key here

# MOCK=1 (the default) means this notebook runs FREE, OFFLINE, and DETERMINISTICALLY over
# tiny local fixtures. This chapter is pure orientation -- there is no live-cloud path, no
# provisioning, and nothing to spend. MOCK stays the switch the rest of the course uses, so
# the muscle memory carries forward.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(32)  # reproducibility for the one place we shuffle the quiz order

DATA = Path("data")
services = json.loads((DATA / "services.json").read_text(encoding="utf-8"))["services"]
prices = json.loads((DATA / "price-sheet.json").read_text(encoding="utf-8"))

print("MOCK =", MOCK, "| offline =", True)
print(f"loaded {len(services)} services and an illustrative price sheet "
      f"({prices['hours_per_month']} h/month)")
print("reminder: price-sheet.json is CLEARLY-FAKE teaching numbers, not live cloud pricing.")
"""))

# 5a. mental model
cells.append(md(r"""
## 🧠 Mental model: the four primitives as a 2x2 map

Hold these four in your head and the whole catalog collapses into patterns you already know (book §32.1):

| Primitive | What you're renting | AWS examples |
|---|---|---|
| **Compute** | Machines to run your code: VMs, containers, functions | EC2, ECS/Fargate, Lambda |
| **Storage** | Places to keep data: object, block, databases | S3, EBS, RDS, DynamoDB |
| **Network** | Connecting and isolating it all: private nets, LBs, DNS | VPC, ALB, Route 53 |
| **Identity** | Who can do what to which resource | IAM |

Everything else is either one of these or a **combo** — a higher-level managed service built by combining them (SageMaker is compute + storage + identity wearing a trench coat). When you meet a new service, don't memorize it: ask *"is this compute, storage, network, or identity?"* That one question is the whole skill.
"""))

# 5b. classify drill -- predict
cells.append(md(r"""
### 🔮 Predict: classify before you peek

Below is a sampler of services from three clouds. For each, **say the primitive out loud** — compute, storage, network, or identity — *before* running the check cell. The names are deliberately a mix of AWS, Azure, and GCP, because the point is that the *same four ideas* map across every provider.

```
GCP Cloud Storage   ·   Azure Entra ID   ·   AWS ALB   ·   AWS Lambda   ·   AWS DynamoDB
```

Jot your five answers, then run the next cell.
"""))

# classifier code
cells.append(code(r"""
# A "classifier" is just a lookup over the fixture -- there's no ML here, and that's the lesson:
# classification is a habit, not a model. We normalize names so a sloppy query still resolves.
_LOOKUP = {s["name"].lower(): s for s in services}

def classify(name: str) -> str:
    # Return the primitive for a service name (or 'unknown' if it's not in our tiny table).
    hit = _LOOKUP.get(name.strip().lower())
    if hit is None:
        return "unknown"
    if hit["primitive"] == "combo":
        return "combo(" + "+".join(hit["parts"]) + ")"
    return hit["primitive"]

quiz = ["GCP Cloud Storage", "Azure Entra ID", "AWS ALB", "AWS Lambda", "AWS DynamoDB"]
for name in quiz:
    print(f"{classify(name):14}  <-  {name}")
"""))

# what you saw
cells.append(md(r"""
**What you just saw.** Object storage on GCP, identity on Azure, a load balancer and a function and a database on AWS — five different vendor names, four primitives, zero surprises once you stop reading them as brand names. Notice `classify` is a dictionary lookup, not intelligence: the *map* lives in your head, and the table just confirms it.
"""))

# full sweep grouped
cells.append(md(r"""
### The whole sampler, grouped

Now sweep the entire fixture and bucket it by primitive. A healthy mental model means none of these placements should feel arbitrary — a new database is storage, a new gateway is network, full stop.
"""))

cells.append(code(r"""
from collections import defaultdict

by_primitive = defaultdict(list)
for s in services:
    by_primitive[s["primitive"]].append(s["name"])

for primitive in ["compute", "storage", "network", "identity", "combo"]:
    names = by_primitive.get(primitive, [])
    print(f"{primitive:8} ({len(names)}): " + ", ".join(names))
"""))

# 6. cost toy intro
cells.append(md(r"""
## 🧠 From map to money: cost is an architecture decision

Same primitives, new lens. In the cloud you rent by the second, so **how you architect** — not just how much traffic you get — sets the bill (book §32.3). The three purchase shapes you must know:

- **on-demand** — flexible, no commitment, *priciest*. The default.
- **spot** — cheap and *interruptible*; perfect for fault-tolerant batch and Celery workers that can be restarted.
- **reserved / savings plans** — commit to a steady baseline for a discount.

We'll build a tiny pure-Python pricing model over the illustrative price sheet, then watch the bill move as we change the *architecture*, not the workload.
"""))

cells.append(code(r"""
HOURS = prices["hours_per_month"]  # ~730 h in a month for an always-on resource

def compute_cost(instance: str, model: str, hours: float = HOURS, count: int = 1) -> float:
    # Monthly cost of `count` instances of a type under a purchase `model`.
    rate = prices["compute"][instance][model]   # KeyError here = you named a model that doesn't exist
    return rate * hours * count

def storage_cost(gb_object: float = 0.0, db_hours: float = 0.0, gb_block: float = 0.0) -> float:
    s = prices["storage"]
    return (gb_object * s["object_per_gb_month"]
            + db_hours * s["managed_db_per_hour"]
            + gb_block * s["block_per_gb_month"])

def network_cost(lb_hours: float = 0.0, egress_gb: float = 0.0) -> float:
    n = prices["network"]
    return lb_hours * n["load_balancer_per_hour"] + egress_gb * n["egress_per_gb"]

# Sanity check: one always-on app instance, three ways to buy it.
for model in ("on_demand", "spot", "reserved"):
    print(f"app_instance {model:10}: ${compute_cost('app_instance', model):8.2f} / month")
"""))

# predict which line dominates
cells.append(md(r"""
### 🔮 Predict: which line item dominates?

Here's a small **always-on agent stack**, the shape you met in Ch 29–31:

- 1x app instance (the FastAPI service) — on-demand, 24/7
- 1x worker instance (Celery) — on-demand, 24/7
- 1x **GPU** instance for a self-hosted model — on-demand, 24/7
- a managed Postgres database — 24/7
- 200 GB of object storage + 100 GB block
- a load balancer 24/7, plus 300 GB/month egress

**Predict:** which *single* line item is the biggest slice of this bill — and roughly what fraction? Write it down, then run the breakdown.
"""))

cells.append(code(r"""
def price_stack(stack: dict) -> dict:
    # Return a {line_item: monthly_usd} breakdown for a described stack.
    b = {}
    b["app (on-demand)"]    = compute_cost("app_instance", stack["app_model"])
    b["worker (on-demand)"] = compute_cost("worker_instance", stack["worker_model"])
    b["gpu (on-demand)"]    = compute_cost("gpu_instance", stack["gpu_model"],
                                           hours=stack["gpu_hours"])
    b["database"]           = storage_cost(db_hours=HOURS)
    b["object+block storage"] = storage_cost(gb_object=stack["object_gb"],
                                             gb_block=stack["block_gb"])
    b["load balancer + egress"] = network_cost(lb_hours=HOURS, egress_gb=stack["egress_gb"])
    return b

baseline = dict(app_model="on_demand", worker_model="on_demand", gpu_model="on_demand",
                gpu_hours=HOURS, object_gb=200, block_gb=100, egress_gb=300)

def show(breakdown: dict, title: str) -> float:
    total = sum(breakdown.values())
    print(title)
    for item, cost in sorted(breakdown.items(), key=lambda kv: -kv[1]):
        share = cost / total * 100
        print(f"  {item:24} ${cost:8.2f}  ({share:4.1f}%)")
    print(f"  {'TOTAL':24} ${total:8.2f}")
    return total

base_total = show(price_stack(baseline), "Always-on agent stack -- all on-demand:")
"""))

cells.append(md(r"""
**What you just saw.** The GPU is the bill. One always-on GPU instance dwarfs the app, the worker, the database, and storage *combined* — which is exactly why self-hosting a model is a decision you make with the invoice open. The line items you'd instinctively worry about (storage, the database) are rounding error next to compute you forgot to right-size.
"""))

# toggle knobs
cells.append(md(r"""
### Turn two knobs (and change nothing about the workload)

Same stack, two architecture decisions:

1. The **worker is fault-tolerant**, so move it to **spot** (it can be restarted if reclaimed) — exactly the FinOps pairing the book calls out for Celery.
2. The **GPU job is batch**, not 24/7 — run it 8 hours a day on spot instead of always-on on-demand.

The traffic is identical. Watch the total.
"""))

cells.append(code(r"""
optimized = dict(baseline)
optimized["worker_model"] = "spot"      # fault-tolerant worker -> spot is free money
optimized["gpu_model"]    = "spot"      # interruptible batch -> spot
optimized["gpu_hours"]    = 8 * 30      # 8 h/day instead of 24/7

opt_total = show(price_stack(optimized), "Same workload, two architecture choices:")
print(f"\nSaved ${base_total - opt_total:.2f}/month "
      f"({(base_total - opt_total) / base_total * 100:.0f}% off) -- by *design*, not by using less.")
"""))

cells.append(md(r"""
**What you just saw.** A double-digit-percent cut without touching a single line of product code or serving one fewer request. That gap — same usage, very different bill — *is* the FinOps thesis: the architecture is the cost lever.
"""))

# shared responsibility sorter
cells.append(md(r"""
## Shared responsibility: which side of the line?

Reliability and security in the cloud are a **shared responsibility** (book §32.2). The provider secures *the* cloud — hardware, data centers, managed-service internals. **You** secure what you put *in* it — IAM policies, network config, your data, your app, your multi-AZ design. Confusion about this line causes real incidents: AWS keeping `us-east-1` up does nothing for you if you ran a single instance in one AZ behind a wide-open security group.

Sort each concern below to the side that owns it.
"""))

cells.append(code(r"""
concerns = [
    "Physical security of the data centers",
    "Patching the hypervisor / host OS",
    "Your IAM policies and who can assume which role",
    "Encrypting your data and managing its keys",
    "Replacing failed disks and network gear",
    "Spreading your service across multiple AZs",
    "Security-group / firewall rules on your VPC",
    "Uptime of the managed-service control plane",
]

# The classification a senior would give. Provider = security *of* the cloud; You = *in* it.
owner = {
    "Physical security of the data centers": "provider",
    "Patching the hypervisor / host OS": "provider",
    "Your IAM policies and who can assume which role": "you",
    "Encrypting your data and managing its keys": "you",
    "Replacing failed disks and network gear": "provider",
    "Spreading your service across multiple AZs": "you",
    "Security-group / firewall rules on your VPC": "you",
    "Uptime of the managed-service control plane": "provider",
}

for side in ("provider", "you"):
    label = "PROVIDER (of the cloud)" if side == "provider" else "YOU (in the cloud)"
    print(label)
    for c in concerns:
        if owner[c] == side:
            print("   -", c)
"""))

cells.append(md(r"""
**What you just saw.** Every item on the *you* side is a configuration choice — and every one of them is a place a single instance, an open security group, or an unencrypted bucket becomes *your* incident, no matter how reliable the provider is. The line isn't about blame; it's about knowing which knobs are yours to turn.
"""))

# senior lens
cells.append(md(r"""
## 🎯 Senior lens: cost and resilience are design, spent deliberately

A senior reads an architecture and sees the bill and the failure modes at the same time — and spends in both *only where it pays*:

- **Spot for anything restartable** (Celery workers, batch GPU jobs); on-demand only for the stateful front door; reserved/savings plans for the steady baseline you'll run all year.
- **Scale-to-zero** the parts with bursty or off-hours traffic (Lambda, stop dev boxes nightly) — you saw the GPU-hours knob do most of the work above.
- **Multi-AZ only where an outage actually costs you.** Spreading the user-facing service across AZs is non-negotiable; spreading a nightly batch job across three AZs just triples a cost for resilience nobody will ever need.
- **Tag everything** (team / environment / feature) so spend is *attributable* — you can't cut waste you can't see.
- **Budget alarms on day one**, before the first deploy, so a runaway loop pages you instead of surprising you on the invoice.

The throughline: in a data center capacity is a sunk cost; in the cloud, *every* primitive you provision is a recurring decision. Make it on purpose.
"""))

# pitfall -- forgotten resource runaway
cells.append(md(r"""
### ⚠️ Pitfall: the resource nobody turned off

The cloud's classic budget-killers don't announce themselves — they *accrue*. A GPU instance spun up for a Friday experiment and left running over the weekend. An oversized database. A dev environment nobody shut down. Egress nobody noticed. Let's model the weekend-GPU runaway and show how a single day-one guardrail would have caught it.
"""))

cells.append(code(r"""
# A dev spins up a GPU box for an experiment on Friday and forgets it. It runs until Monday.
forgotten_gpu_hours = 3 * 24  # Fri evening -> Mon morning, ~72 h
leak = compute_cost("gpu_instance", "on_demand", hours=forgotten_gpu_hours)
print(f"One forgotten GPU box, one weekend: ${leak:.2f} -- for zero delivered value.")

# Annualize the habit: this happening, unnoticed, a couple times a month.
print(f"If this happens ~2x/month unnoticed: ${leak * 2 * 12:.2f}/year of pure waste.")

# The day-one guardrail: a budget alarm at a threshold you set BEFORE deploying anything.
BUDGET_ALARM_USD = 50.0

def budget_alarm(month_to_date_spend: float, threshold: float = BUDGET_ALARM_USD) -> str:
    if month_to_date_spend >= threshold:
        return (f"ALARM: month-to-date ${month_to_date_spend:.2f} >= ${threshold:.2f} "
                f"-> page the owner, find the resource, kill it.")
    return f"ok: ${month_to_date_spend:.2f} under ${threshold:.2f}"

# The alarm fires partway through the weekend, long before the full bill lands.
print(budget_alarm(leak))
"""))

cells.append(md(r"""
**What you just saw.** The leak is silent and the annualized number is real money — but the fix is trivial and *cheap to build in early*: a budget alarm set on day one fires while the box is still warm, not on next month's invoice. Pair it with tags (every resource has an owner) and an auto-stop schedule for non-prod, and the whole class of "who left this on?" surprises mostly disappears.
"""))

# map capstone onto primitives (PLAN requires)
cells.append(md(r"""
## Closing the loop: the capstone, in four primitives

Everything you'll deploy later is just these four primitives in a trench coat. Here's the capstone stack (the agent service from Parts VII–VIII) mapped onto the map — the exact lens you'll carry into Ch 33's AWS deep-dive.
"""))

cells.append(code(r"""
capstone_components = [
    ("FastAPI agent service (Fargate)", "compute"),
    ("Celery workers (Fargate, spot)",  "compute"),
    ("Postgres (RDS)",                  "storage"),
    ("Artifacts bucket (S3)",           "storage"),
    ("Redis cache/queue",               "storage"),
    ("VPC + ALB + Route 53",            "network"),
    ("IAM roles per component",         "identity"),
]

print("The capstone, classified:")
for component, primitive in capstone_components:
    print(f"  {primitive:9} <- {component}")

covered = {p for _, p in capstone_components}
print("\nPrimitives exercised:", ", ".join(sorted(covered)))
print("Same four ideas. Ch 33 just gives them their AWS names and a least-privilege role each.")
"""))

# recap
cells.append(md(r"""
## Recap

- **Four primitives** — compute, storage, network, identity — classify any service on any cloud; *combos* are just managed bundles of them.
- Classification is a **habit, not a model**: ask "which primitive?" and the 200-service catalog collapses.
- **Cost is an architecture decision.** on-demand / spot / reserved is a *design* choice; moving a fault-tolerant worker to spot and a batch GPU off 24/7 cut the bill double digits with identical usage.
- In an agent stack, **always-on compute (the GPU) dominates** — read the bill with that prior.
- **Shared responsibility:** the provider secures *of* the cloud; you secure *in* it — and every "you" item is a config choice that can become your incident.
- **Forgotten/idle resources** are the silent budget-killer; a **day-one budget alarm** + tags + off-hours auto-stop catch them.
"""))

# exercises
cells.append(md(r"""
## Exercises

1. **Classify a service you've never seen.** Add one real service *not* in `data/services.json` (e.g. "AWS Step Functions", "GCP Pub/Sub", "Azure Cosmos DB"). 🔮 Predict its primitive (or *combo*), add it to the fixture, and confirm `classify` agrees. Defend any *combo* call by naming its parts.
2. **Find where the bill quietly grows.** In `baseline`, which *single* knob would you change to most reduce cost without hurting a user-facing SLA? Change it, re-run `show`, and explain why that line was safe to cut (hint: which primitive, and is it user-facing?).
3. **Right-size, don't just discount.** The GPU is the bill. Instead of spot, model *removing* the self-hosted GPU entirely and paying a per-token API instead (invent a fake `per_1k_tokens` price and a monthly token volume). At what volume does self-hosting win? Where's the crossover?
4. **Draw the shared-responsibility line.** Add two new concerns to the sorter — one clearly the provider's, one clearly yours — and one *genuinely ambiguous* one (e.g. "OS patching on a managed database"). Argue which side the ambiguous one lands on and why the line can shift by service.
"""))

cells.append(code("# Exercise 1 -- add a new service to the fixture and classify it."))
cells.append(code("# Exercise 2 -- change one knob in `baseline`, re-run `show`, justify the cut."))
cells.append(code("# Exercise 3 -- model API-per-token vs self-hosted GPU; find the crossover."))
cells.append(code("# Exercise 4 -- extend the shared-responsibility sorter with an ambiguous concern."))

# next
cells.append(md(r"""
## Next

- **Next chapter:** [`../33-aws-for-ai-engineers/33-01-iam-and-least-privilege.ipynb`](../33-aws-for-ai-engineers/33-01-iam-and-least-privilege.ipynb) — the *identity* primitive made concrete: write a least-privilege IAM policy and prove it, still with no AWS account. The capstone components you just classified each get their own tightly-scoped role there.
- **The cost lens returns:** in Ch 40's token accounting and the [`blueprints/observability-stack/`](../../../blueprints/observability-stack/) cost metrics — same FinOps habit, applied to per-token model spend.
- **Feeds the capstone:** this is the four-primitive + FinOps lens you apply when reading the AWS deploy in [`capstone/`](../../../capstone/) (Appendix C). You just mapped its pieces onto the map; Ch 33 gives them AWS names. See book §32.1–§32.3.
"""))

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(notebook, f, ensure_ascii=False, indent=1)
    f.write("\n")

print("wrote", OUT)
print("cells:", len(cells))
