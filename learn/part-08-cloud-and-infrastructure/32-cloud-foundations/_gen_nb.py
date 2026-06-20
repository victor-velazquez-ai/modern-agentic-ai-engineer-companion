"""One-shot generator for 32-01-four-primitives-and-finops.ipynb.

Builds a valid nbformat-4 notebook with cleared outputs. This file is deleted
after it runs; it exists only to keep the source-line splitting exact.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "32-01-four-primitives-and-finops.ipynb")


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(text)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _lines(text),
    }


def _lines(text: str) -> list:
    text = text.strip("\n")
    parts = text.split("\n")
    return [p + "\n" for p in parts[:-1]] + [parts[-1]]


cells = []

# 1. Title + header --------------------------------------------------------
cells.append(md(
    "# The four primitives, then the bill\n"
    "\n"
    "> \U0001F4D3 *Companion to* **Modern Agentic AI Engineer** · Ch 32 §§32.1–32.3 · type: concept-lab\n"
    "\n"
    "**The promise:** by the end you can classify any unfamiliar cloud service into "
    "**compute / storage / network / identity** on sight, and sketch a defensible monthly "
    "cost for a small agent stack — including the forgotten-resource trap — before you "
    "provision anything.\n"
    "\n"
    "This is the orientation notebook for Part VIII. It runs **fully offline and free**: no "
    "cloud account, no SDK, no API key, no spend. Everything is tiny local Python over two "
    "committed fixture files."
))

# 2. Why this matters ------------------------------------------------------
cells.append(md(
    "## \U0001F9E0 Why this matters\n"
    "\n"
    "A cloud console shows you 200+ services and dares you to feel behind. Strip away the "
    "marketing and every cloud rents you exactly **four kinds of thing**: *compute* (machines "
    "to run code), *storage* (places to keep data), *network* (connecting and isolating it), "
    "and *identity* (who can do what to which resource). Every service — on AWS, Azure, or "
    "GCP — is a flavor of one of those four, or a managed combination of them.\n"
    "\n"
    "The second idea is that **cost is a variable you control with architecture**, not a bill "
    "that happens to you. In a data center capacity is a fixed cost you already paid; in the "
    "cloud you rent by the second, so the *shape* of your design — spot vs on-demand, "
    "scale-to-zero, where you put multi-AZ — drives the invoice. Hold the four primitives and "
    "the FinOps mindset in your head and the rest of Part VIII (the AWS deploy in Ch 33–36) "
    "stops being intimidating. See §§32.1–32.3."
))

# 3. Objectives + prereqs --------------------------------------------------
cells.append(md(
    "## Objectives & prereqs\n"
    "\n"
    "**By the end you can:**\n"
    "- Classify a service name into compute / storage / network / identity (or a combo) on sight.\n"
    "- Read the three cost shapes — **on-demand**, **spot**, **reserved** — as functions of usage.\n"
    "- Estimate the monthly bill of a small always-on agent stack and see which line item dominates.\n"
    "- Sort concerns across the **shared-responsibility** line (provider's job vs your job).\n"
    "- Spot where a bill quietly grows (idle GPU, oversized DB, egress) and what guardrail catches it.\n"
    "\n"
    "**Prereqs:** Chapter 32 read. Ch 29–31 (distributed systems, data layer, workers) make the "
    "examples concrete — the stack we cost is that capstone shape — but are not strictly required.\n"
    "\n"
    "**Packages:** the standard library only. No SDKs, no network. The fixtures live in `data/`."
))

# 4. Setup -----------------------------------------------------------------
cells.append(code(
    "# Setup — imports, env, and the MOCK switch.\n"
    "import json\n"
    "import os\n"
    "import random\n"
    "from pathlib import Path\n"
    "\n"
    "from dotenv import load_dotenv\n"
    "\n"
    "load_dotenv()  # reads a local .env if present; never hardcode keys\n"
    "\n"
    "# This notebook is offline by design: there is no live path and no key to set.\n"
    "# We still honor the companion-wide MOCK switch so every notebook reads the same.\n"
    "# MOCK=1 (default) is the only supported mode here — nothing ever calls a cloud.\n"
    "MOCK = os.getenv(\"COMPANION_MOCK\", \"1\") == \"1\"\n"
    "\n"
    "random.seed(32)  # the one stochastic cell (a usage sample) is reproducible\n"
    "\n"
    "DATA = Path(\"data\")\n"
    "services = json.loads((DATA / \"services.json\").read_text(encoding=\"utf-8\"))[\"services\"]\n"
    "prices = json.loads((DATA / \"price-sheet.json\").read_text(encoding=\"utf-8\"))\n"
    "\n"
    "print(f\"MOCK mode: {MOCK}  (offline, free — no cloud account, no SDK, no spend)\")\n"
    "print(f\"loaded {len(services)} service entries and a {prices['currency']} price sheet\")\n"
    "print(f\"price sheet is ILLUSTRATIVE / fake — do not use for real estimates\")"
))

# 5a. Mental model: the four primitives -----------------------------------
cells.append(md(
    "## \U0001F9E0 Mental model: four primitives, one map\n"
    "\n"
    "Don't memorize services — **classify** them. Picture a 2×2 map; every service drops onto "
    "one of four squares (or is a managed *combo* of them):\n"
    "\n"
    "| Primitive | What you're renting | AWS examples |\n"
    "|---|---|---|\n"
    "| **Compute** | machines to run your code | EC2, Fargate, Lambda |\n"
    "| **Storage** | places to keep data | S3, EBS, RDS, DynamoDB |\n"
    "| **Network** | connecting & isolating it all | VPC, ALB, Route 53 |\n"
    "| **Identity** | who can do what to which resource | IAM |\n"
    "\n"
    "A new database is storage; a new container service is compute; a new gateway is network. "
    "This one habit turns the catalog into four patterns you already understand — and lets you "
    "learn *any* cloud by mapping its names onto the same four ideas."
))

# 5b. classify() drill -----------------------------------------------------
cells.append(md(
    "### A `classify()` drill\n"
    "\n"
    "Below is a tiny offline classifier: it just looks the name up in `data/services.json`. "
    "The point isn't the lookup — it's *your* prediction. We'll quiz a list of real "
    "AWS/Azure/GCP names."
))

cells.append(code(
    "LOOKUP = {s[\"name\"]: s for s in services}\n"
    "\n"
    "\n"
    "def classify(name: str) -> str:\n"
    "    \"\"\"Return the primitive for a known service name (offline lookup, no SDK).\n"
    "\n"
    "    Returns 'compute' | 'storage' | 'network' | 'identity' | 'combo' | 'unknown'.\n"
    "    A real engineer does this in their head; the table just checks the answer.\n"
    "    \"\"\"\n"
    "    entry = LOOKUP.get(name)\n"
    "    return entry[\"primitive\"] if entry else \"unknown\"\n"
    "\n"
    "\n"
    "quiz = [\n"
    "    \"AWS Lambda\",\n"
    "    \"AWS S3\",\n"
    "    \"AWS Route 53\",\n"
    "    \"AWS IAM\",\n"
    "    \"Azure Blob Storage\",\n"
    "    \"GCP Compute Engine\",\n"
    "    \"AWS DynamoDB\",\n"
    "    \"AWS SageMaker\",\n"
    "]\n"
    "print(f\"{len(quiz)} services to classify — predict each before running the next cell.\")"
))

# 5c. Predict #1 -----------------------------------------------------------
cells.append(md(
    "### \U0001F52E Predict\n"
    "\n"
    "For each name in `quiz`, **say the primitive out loud** (compute / storage / network / "
    "identity — or *combo*). Two are worth pausing on: which one is a managed *combination* of "
    "primitives rather than a single one, and how would you classify a service whose name you've "
    "never seen? Write your eight answers down, then run the check."
))

cells.append(code(
    "for name in quiz:\n"
    "    entry = LOOKUP[name]\n"
    "    primitive = entry[\"primitive\"]\n"
    "    if primitive == \"combo\":\n"
    "        label = \"combo (\" + \" + \".join(entry[\"parts\"]) + \")\"\n"
    "    else:\n"
    "        label = primitive\n"
    "    print(f\"{name:24s} -> {label:28s} {entry['note']}\")"
))

cells.append(md(
    "**What you just saw.** Eight names, four patterns. `AWS SageMaker` is the tell: a "
    "high-level managed service is just primitives wired together (compute + storage + "
    "identity), so you classify it by what it's *made of*. And the move for an unfamiliar name "
    "is the same one every time — ask \"machine, data, wiring, or permissions?\" — not "
    "\"let me go memorize this service.\""
))

# 6a. Pricing toy ----------------------------------------------------------
cells.append(md(
    "## The three cost shapes, as functions\n"
    "\n"
    "Compute is rented three ways, and the choice is pure architecture:\n"
    "\n"
    "- **on-demand** — flexible, pay by the second, *priciest*. The default.\n"
    "- **spot** — cheap, but the provider can reclaim it with little warning. Perfect for "
    "fault-tolerant batch and **Celery** workers (Ch 31) that can just retry.\n"
    "- **reserved / savings plan** — commit to a steady baseline for a discount. For the load "
    "that's *always* on.\n"
    "\n"
    "Here they are as plain Python over the fake price sheet — no cloud, no SDK."
))

cells.append(code(
    "HOURS = prices[\"hours_per_month\"]  # ~730 hours in a month\n"
    "\n"
    "\n"
    "def compute_cost(instance: str, model: str, hours: float) -> float:\n"
    "    \"\"\"Monthly cost of one compute instance under a purchase model.\n"
    "\n"
    "    model is 'on_demand' | 'spot' | 'reserved'. hours is how many hours/month it runs\n"
    "    (an always-on box is HOURS; an off-hours dev box far fewer).\n"
    "    \"\"\"\n"
    "    rate = prices[\"compute\"][instance][model]\n"
    "    return rate * hours\n"
    "\n"
    "\n"
    "# Same always-on app instance, three purchase models:\n"
    "for model in (\"on_demand\", \"spot\", \"reserved\"):\n"
    "    monthly = compute_cost(\"app_instance\", model, HOURS)\n"
    "    print(f\"app_instance, {model:10s}, always-on: ${monthly:7.2f}/mo\")"
))

cells.append(md(
    "**What you just saw.** The *identical* machine costs roughly 3× more on-demand than on "
    "spot. You didn't change the workload — you changed a purchasing decision. That is what "
    "\"cost is an architecture decision\" means in one line."
))

# 6b. Cost the stack + Predict #2 -----------------------------------------
cells.append(md(
    "### \U0001F52E Predict: which line item dominates?\n"
    "\n"
    "Now cost a small **always-on agent stack** — the Ch 29–31 shape: a couple of app "
    "instances behind a load balancer, a managed database, some object storage, a pool of "
    "Celery workers, and the data that flows out to users (egress).\n"
    "\n"
    "**Predict before running:** of `app`, `workers`, `database`, `storage`, `load_balancer`, "
    "`egress` — which single line item is the **largest** in this baseline? Most people guess "
    "wrong. Write your pick down."
))

cells.append(code(
    "def price_stack(spec: dict) -> dict:\n"
    "    \"\"\"Cost a small stack from a spec. Returns {line_item: monthly_usd}.\n"
    "\n"
    "    Pure arithmetic over the fake price sheet — deterministic, offline.\n"
    "    \"\"\"\n"
    "    c, s, n = prices[\"compute\"], prices[\"storage\"], prices[\"network\"]\n"
    "    bill = {}\n"
    "    bill[\"app\"] = c[\"app_instance\"][spec[\"app_model\"]] * HOURS * spec[\"app_count\"]\n"
    "    bill[\"workers\"] = (\n"
    "        c[\"worker_instance\"][spec[\"worker_model\"]] * HOURS * spec[\"worker_count\"]\n"
    "    )\n"
    "    bill[\"database\"] = s[\"managed_db_per_hour\"] * HOURS\n"
    "    bill[\"storage\"] = s[\"object_per_gb_month\"] * spec[\"storage_gb\"]\n"
    "    bill[\"load_balancer\"] = n[\"load_balancer_per_hour\"] * HOURS\n"
    "    bill[\"egress\"] = n[\"egress_per_gb\"] * spec[\"egress_gb\"]\n"
    "    return bill\n"
    "\n"
    "\n"
    "def show_bill(bill: dict, title: str) -> float:\n"
    "    total = sum(bill.values())\n"
    "    print(title)\n"
    "    for item, cost in sorted(bill.items(), key=lambda kv: -kv[1]):\n"
    "        share = cost / total * 100 if total else 0\n"
    "        bar = \"█\" * round(share / 4)\n"
    "        print(f\"  {item:14s} ${cost:8.2f}/mo  {share:5.1f}%  {bar}\")\n"
    "    print(f\"  {'TOTAL':14s} ${total:8.2f}/mo\")\n"
    "    return total\n"
    "\n"
    "\n"
    "baseline_spec = {\n"
    "    \"app_count\": 2,\n"
    "    \"app_model\": \"on_demand\",\n"
    "    \"worker_count\": 3,\n"
    "    \"worker_model\": \"on_demand\",  # workers on-demand to start — we'll fix this\n"
    "    \"storage_gb\": 200,\n"
    "    \"egress_gb\": 300,\n"
    "}\n"
    "baseline = price_stack(baseline_spec)\n"
    "baseline_total = show_bill(baseline, \"Baseline always-on agent stack:\")"
))

cells.append(md(
    "**What you just saw.** Compute (app + workers) dominates a steady stack — it's the "
    "always-on, per-hour line that never sleeps. Storage and egress are smaller *here* but they "
    "scale with usage, and egress in particular is the one that surprises people as traffic "
    "grows. Notice nothing is \"wrong\" yet — it's just expensive by default."
))

# 6c. Toggle the knobs -----------------------------------------------------
cells.append(md(
    "### Turn two knobs, re-read the bill\n"
    "\n"
    "Two FinOps moves, no code change to the *workload*:\n"
    "1. Move the **Celery workers to spot** — they're fault-tolerant and retry, so interruption "
    "is fine.\n"
    "2. Put the app instances on a **reserved** commitment — that load is always on anyway."
))

cells.append(code(
    "optimized_spec = dict(baseline_spec)\n"
    "optimized_spec[\"worker_model\"] = \"spot\"       # fault-tolerant -> spot\n"
    "optimized_spec[\"app_model\"] = \"reserved\"      # steady baseline -> reserved\n"
    "\n"
    "optimized = price_stack(optimized_spec)\n"
    "optimized_total = show_bill(optimized, \"After spot workers + reserved app:\")\n"
    "\n"
    "saved = baseline_total - optimized_total\n"
    "pct = saved / baseline_total * 100\n"
    "print()\n"
    "print(f\"Same workload, two purchasing decisions: -${saved:.2f}/mo ({pct:.0f}% cheaper).\")"
))

cells.append(md(
    "**What you just saw.** Same machines, same traffic, a materially smaller bill — from "
    "*where* you placed spot and reserved. Matching the purchase model to the workload's "
    "fault-tolerance is the highest-leverage FinOps move on compute, and it's a design choice "
    "you make before you ever click \"launch.\""
))

# 7. Shared-responsibility sorter -----------------------------------------
cells.append(md(
    "## Shared responsibility: which side of the line?\n"
    "\n"
    "Cloud reliability is a **shared responsibility**, and confusion about the line causes real "
    "incidents. The provider secures the cloud *itself* — hardware, data centers, managed-service "
    "internals. **You** are responsible for security and reliability *in* the cloud — your IAM "
    "policies, your network config, your data, your app, your multi-AZ design. AWS keeping a "
    "region up does not save you if you ran a single instance in one AZ with a wide-open "
    "security group."
))

cells.append(code(
    "# Sort each concern to the side of the line it belongs on.\n"
    "concerns = {\n"
    "    \"physical data-center security\": \"provider\",\n"
    "    \"hardware & hypervisor patching\": \"provider\",\n"
    "    \"managed-service internals (e.g. RDS engine uptime)\": \"provider\",\n"
    "    \"region/AZ power & networking\": \"provider\",\n"
    "    \"your IAM policies & least privilege\": \"you\",\n"
    "    \"security-group / VPC configuration\": \"you\",\n"
    "    \"your application code & dependencies\": \"you\",\n"
    "    \"multi-AZ design & data backups\": \"you\",\n"
    "}\n"
    "\n"
    "for side in (\"provider\", \"you\"):\n"
    "    header = \"PROVIDER's job (security OF the cloud)\" if side == \"provider\" else \"YOUR job (security IN the cloud)\"\n"
    "    print(header)\n"
    "    for concern, owner in concerns.items():\n"
    "        if owner == side:\n"
    "            print(f\"  • {concern}\")\n"
    "    print()"
))

cells.append(md(
    "**What you just saw.** A clean split. The pattern: the provider owns everything *below* "
    "the API you call; you own everything you *configure* through it. Most cloud breaches and "
    "outages live entirely on the \"you\" side — a misconfigured bucket policy or a single-AZ "
    "deployment, never a data center that caught fire."
))

# 8. Pitfall: runaway idle resources --------------------------------------
cells.append(md(
    "## ⚠️ Pitfall: idle & forgotten resources\n"
    "\n"
    "The cloud's classic budget-killers don't announce themselves — a **GPU instance left "
    "running over a weekend**, an oversized DB, a dev box nobody shut down, egress nobody "
    "watched. They just accrue. Let's model the weekend-GPU runaway and show how a **day-one "
    "budget alarm** would have caught it."
))

cells.append(code(
    "gpu_rate = prices[\"compute\"][\"gpu_instance\"][\"on_demand\"]\n"
    "\n"
    "# A GPU box spun up Friday for an experiment, forgotten until Monday morning.\n"
    "weekend_hours = 60  # Fri evening -> Mon morning\n"
    "forgotten_cost = gpu_rate * weekend_hours\n"
    "\n"
    "# If left a full month (the dev-environment-nobody-killed scenario):\n"
    "month_cost = gpu_rate * HOURS\n"
    "\n"
    "BUDGET_ALARM = 200.00  # a day-one monthly budget threshold for this account\n"
    "\n"
    "print(f\"Forgotten GPU, one weekend ({weekend_hours}h): ${forgotten_cost:,.2f}\")\n"
    "print(f\"Same GPU left a full month:           ${month_cost:,.2f}\")\n"
    "print()\n"
    "# A budget alarm fires when projected month-to-date spend crosses the threshold.\n"
    "if month_cost > BUDGET_ALARM:\n"
    "    day_crossed = BUDGET_ALARM / gpu_rate / 24\n"
    "    print(f\"⚠️  budget alarm (${BUDGET_ALARM:.0f}) would page you ~day {day_crossed:.1f} — not on the invoice.\")\n"
    "else:\n"
    "    print(\"Under budget — no alarm.\")"
))

cells.append(md(
    "**What you just saw.** One forgotten GPU dwarfs the entire optimized stack above. The fix "
    "isn't vigilance — it's structure: set **billing alarms on day one**, give every resource an "
    "**owner via tags** so you can attribute spend, and **auto-stop non-production "
    "environments off-hours**. Cost discipline is far cheaper to build in early than to "
    "retrofit after a five-figure surprise."
))

# 9. Senior lens -----------------------------------------------------------
cells.append(md(
    "## \U0001F3AF Senior lens\n"
    "\n"
    "A senior engineer treats **cost as a design input, not a monthly surprise**. They reach "
    "for spot on anything fault-tolerant (Celery workers, batch), reserved on steady baselines, "
    "and scale-to-zero (Lambda/Fargate) on spiky or dev workloads — and they put **multi-AZ "
    "only where it pays**, because resilience also costs money and not every dev box needs it. "
    "They tag every resource by team / environment / feature so spend is *attributable* and "
    "waste is *findable*, and they wire a **budget alarm before the first deploy**, so a "
    "runaway loop pages a human instead of accruing silently.\n"
    "\n"
    "The deeper habit is the one this whole notebook trains: when a new service or bill lands "
    "on their desk, they don't reach for docs — they ask \"which primitive, and what shape of "
    "cost?\" That single question is what makes a 200-service cloud legible and a five-figure "
    "invoice predictable."
))

# 10. Recap ----------------------------------------------------------------
cells.append(md(
    "## Recap\n"
    "\n"
    "- Every cloud rents **four primitives** — compute, storage, network, identity; every service "
    "is a flavor or a managed combo. Classify, don't memorize.\n"
    "- Compute comes in three cost shapes: **on-demand** (flexible, priciest), **spot** (cheap, "
    "interruptible — great for Celery/batch), **reserved** (commit for a discount on baseline).\n"
    "- **Cost is an architecture decision:** the same workload got materially cheaper by moving "
    "purchase models, not by changing the work.\n"
    "- Reliability is a **shared responsibility** — the provider secures the cloud; you secure "
    "what you configure *in* it (IAM, network, multi-AZ, data).\n"
    "- The budget-killers are **idle & forgotten** resources; a **day-one budget alarm** plus "
    "tags and off-hours auto-stop catch them before the invoice does."
))

# 11. Exercises ------------------------------------------------------------
cells.append(md(
    "## Exercises\n"
    "\n"
    "Each one *changes* something and asks you to predict the result first.\n"
    "\n"
    "1. **Which primitive is service X?** Add three services you've seen but don't know "
    "(search their one-line description) to `data/services.json`, then classify them by hand "
    "*before* checking. Did any turn out to be a *combo*?\n"
    "2. **Where would the bill quietly grow?** Triple `egress_gb` in `baseline_spec` and "
    "re-cost the stack. Predict whether egress overtakes compute, then check — and explain why "
    "egress is the line that surprises growing products.\n"
    "3. **Scale-to-zero math.** A dev box runs only 8 work-hours × 22 weekdays a month instead "
    "of always-on. Compute its `compute_cost` and compare to always-on. What's the percentage "
    "saving from off-hours auto-stop alone?\n"
    "4. **Tune the alarm.** Pick a `BUDGET_ALARM` that would catch the *weekend* GPU runaway "
    "within 24 hours. What threshold (and what tag-based attribution) would you actually set "
    "for a real team account?"
))

cells.append(code("# Exercise scratch space — your code here.\n"))
cells.append(code("# Exercise scratch space — your code here.\n"))

# 12. Next -----------------------------------------------------------------
cells.append(md(
    "## Next\n"
    "\n"
    "- **Book:** you now hold the lens for the rest of Part VIII — §32.1 (four primitives), "
    "§32.2 (regions/AZs, shared responsibility), §32.3 (cost + FinOps). Chapter 33 goes deep "
    "on **AWS**, the platform the capstone deploys to.\n"
    "- **Map the capstone onto the four primitives.** When you read the AWS deploy in "
    "[`capstone/`](../../../capstone/) (Appendix C), tag each piece: the agent service is "
    "**compute** (Fargate/Lambda), Postgres + object store are **storage**, the VPC + load "
    "balancer are **network**, and the task/exec roles are **identity**. Four squares, the "
    "whole deployment.\n"
    "- **Where the cost lens reappears:** token accounting in Ch 40 and the cost metrics in "
    "[`blueprints/observability-stack/`](../../../blueprints/observability-stack/) are this "
    "same FinOps habit, applied to per-token model spend instead of per-hour instances."
))

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
    json.dump(notebook, f, indent=1, ensure_ascii=False)
    f.write("\n")

print("wrote", OUT)
