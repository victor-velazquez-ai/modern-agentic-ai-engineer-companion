"""Generate 49-01-staying-current-worksheet.ipynb.

Worksheet-type notebook for Ch 49 (worksheet-only chapter; see PLAN.md). It hosts the
chapter's fill-in prompts on the notebook surface. No model calls, no fake paper feed —
the only code is tiny, offline, stdlib-only helpers that turn the reader's own answers
into a printed tracking system. Defaults to MOCK so it runs free/offline with no key.

Run:  python _build_nb_01.py   (writes the .ipynb next to this file)
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "49-01-staying-current-worksheet.ipynb"


def md(*lines):
    return {"cell_type": "markdown", "metadata": {}, "source": _src(lines)}


def code(*lines):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _src(lines),
    }


def _src(lines):
    """nbformat source = list of strings, each (except the last) ending in \n."""
    text = "\n".join(lines)
    parts = text.split("\n")
    return [p + "\n" for p in parts[:-1]] + [parts[-1]] if parts else []


cells = []

# 1) Title + header --------------------------------------------------------------
cells.append(md(
    "# Build your staying-current system: a fill-in worksheet",
    "",
    "> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 49 §49.2 · type: worksheet*",
    "",
    "*One-line promise:* turn the chapter's *system for staying current* into **your** "
    "system — a handful of sources, one weekly slot, a depreciation schedule, and a "
    "model-swap drill — captured here in cells you fill in and the notebook prints back as a plan.",
    "",
    "> ⚠️ **This is a worksheet, not a lab.** There is *nothing to execute against an "
    "API and no fake \"paper feed\"* — Ch 49 teaches a personal process, and the honest "
    "companion is a thing you **fill in**, not a kernel you run (see this chapter's "
    "`PLAN.md` for why a forced notebook here would be theatre). The few code cells just "
    "echo *your* answers back as a structured plan, fully offline.",
))

# 2) Why this matters ------------------------------------------------------------
cells.append(md(
    "## 🧠 Why this matters",
    "",
    "This field moves faster than any in software history, and that produces two failure "
    "modes: engineers who chase every release and burn out, and engineers who stop looking "
    "and quietly obsolete themselves. The senior path is neither — it's a **system** that "
    "filters aggressively, anchors on fundamentals, and treats the firehose as a *queryable "
    "resource* rather than a reading obligation (§49). The system only works if it's *yours* "
    "and *small enough to actually run weekly*. So you don't read this chapter — you "
    "**instantiate** it: pick your sources, name your weekly slot, sort what depreciates "
    "slowly from what you'll look up on demand, and set the model-swap drill that keeps your "
    "architecture honest.",
))

# 3) Objectives + prereqs --------------------------------------------------------
cells.append(md(
    "## Objectives & prereqs",
    "",
    "**By the end you can:**",
    "- Apply the **20-minute paper-reading method** and the **four filter questions** as a "
    "repeatable checklist (§49.1).",
    "- Stand up a personal **tracking pipeline**: 2–3 high-signal sources, one weekly batch "
    "slot, *prune-or-keep* discipline (§49.2).",
    "- Sort your learning into a **depreciation schedule** — slow fundamentals to invest in "
    "vs. fast layers to look up on demand (§49.2).",
    "- Run the **resume-driven-adoption gate** and the **model-swap drill** from the chapter's "
    "closing #checklist.",
    "",
    "**Prereqs:** none to *run* — nothing calls a network. Conceptually this is the capstone "
    "of the technical material: it reframes every prior chapter as *fundamentals that "
    "depreciate slowly*. Bring your **own** current stack and reading list to fill in.",
    "",
    "**Cost:** none. Fully offline — no API key, no model call, no package beyond the stdlib.",
))

# 4) Setup -----------------------------------------------------------------------
cells.append(md("## Setup"))
cells.append(code(
    "import json",
    "import os",
    "from datetime import date",
    "",
    "from dotenv import load_dotenv",
    "",
    "load_dotenv()  # reads a git-ignored .env if present; never hardcode keys",
    "",
    "# MOCK=1 (the default) keeps this notebook 100% offline. A worksheet has nothing to",
    "# call live, so MOCK only gates an OPTIONAL last cell that can ask an LLM to first-pass",
    "# a paper for you (the chapter's 'use an LLM as your first-pass reader' tip, §49.1).",
    "# With MOCK=1 that cell returns a canned summary; no key is ever required to run this.",
    "MOCK = os.getenv(\"COMPANION_MOCK\", \"1\") == \"1\"",
    "MODEL = os.getenv(\"COMPANION_MODEL\", \"claude-opus-4-8\")  # never called in MOCK",
    "",
    "TODAY = date(2026, 6, 20)  # fixed so this worksheet renders deterministically",
    "VERSION_STAMP = \"as of early 2026 — re-check; prune rather than accumulate\"",
    "",
    "print(\"MOCK =\", MOCK, \"| nothing here calls a network unless you opt in below\")",
    "if not MOCK and not os.getenv(\"ANTHROPIC_API_KEY\"):",
    "    raise SystemExit(\"MOCK=0 needs ANTHROPIC_API_KEY in your environment / .env\")",
))

# 5) Body ------------------------------------------------------------------------

# --- 49.1 paper-reading method ---
cells.append(md(
    "## Part 1 — Reading papers efficiently (§49.1)",
    "",
    "You don't read papers cover to cover; you **extract claims and judge them**. The method "
    "is twenty minutes, not three hours:",
    "",
    "1. **Abstract** — what is the claim?",
    "2. **Results tables & figures** — does the evidence back it?",
    "3. **Limitations** — what do the authors admit?",
    "4. **Method in full** — *only* if it survived the screen **and** matters to your work.",
    "",
    "Then the **four filter questions**. The cell below holds them as a reusable checklist; "
    "later you'll run a real (or recent) paper through it.",
))
cells.append(code(
    "# The chapter's four filter questions (§49.1), verbatim in intent. Reusable as a gate.",
    "FILTER_QUESTIONS = [",
    "    \"Is the baseline fair, or a strawman with a crippled prompt?\",",
    "    \"Is the improvement large enough to survive contact with production?\",",
    "    \"Is there code, and has anyone independently reproduced it?\",",
    "    \"Does it hold beyond one benchmark?\",",
    "]",
    "",
    "PAPER_READING_METHOD = [\"abstract\", \"results/figures\", \"limitations\",",
    "                       \"method (only if it survives the screen)\"]",
    "",
    "for i, q in enumerate(FILTER_QUESTIONS, 1):",
    "    print(f\"  Q{i}. {q}\")",
))

cells.append(md(
    "### ✍️ Run a paper through the gate",
    "",
    "Pick a paper you've seen hyped this month (or a recent one you half-believe). Fill in a "
    "*yes/no* and a one-line note per filter question. The helper tallies how many it passes "
    "— and the chapter's bar is **all four**, not three.",
))
cells.append(code(
    "# ✍️ FILL IN: replace each (answer, note) with your honest read of one paper.",
    "PAPER_TITLE = \"<paper title / arXiv id>\"  # ✍️",
    "",
    "# answer ∈ {\"yes\", \"no\", \"unsure\"}; note is your one-liner of evidence.",
    "paper_review = {",
    "    FILTER_QUESTIONS[0]: (\"unsure\", \"<is the baseline fair?>\"),       # ✍️",
    "    FILTER_QUESTIONS[1]: (\"unsure\", \"<would the gain survive prod?>\"),  # ✍️",
    "    FILTER_QUESTIONS[2]: (\"unsure\", \"<code? independent repro?>\"),      # ✍️",
    "    FILTER_QUESTIONS[3]: (\"unsure\", \"<holds beyond one benchmark?>\"),   # ✍️",
    "}",
    "",
    "",
    "def score_paper(review):",
    "    passed = sum(1 for ans, _ in review.values() if ans.strip().lower() == \"yes\")",
    "    verdict = \"READ IN FULL\" if passed == len(review) else \"skim / move on\"",
    "    return passed, verdict",
    "",
    "",
    "passed, verdict = score_paper(paper_review)",
    "print(f\"{PAPER_TITLE}: passed {passed}/{len(paper_review)} filters -> {verdict}\")",
    "for q, (ans, note) in paper_review.items():",
    "    print(f\"  [{ans:>6}] {q}\\n          {note}\")",
))

# --- demo-vs-distribution ---
cells.append(md(
    "### 🔮 Predict — the demo-vs-distribution test",
    "",
    "The reliable hype filter is the gap between a **demo** and a **distribution**: a demo "
    "proves something is possible *once, on chosen inputs*; engineering needs it to work "
    "across the ugly distribution of real inputs at survivable cost (§49.1).",
    "",
    "> Below are four real-flavoured claims. **Predict**, for each, whether it's likely "
    "*demo-deep* or *distribution-deep* — write your guess down — **before** running the cell. "
    "The one-line test to apply: *show me the failure modes.*",
))
cells.append(code(
    "# The one-line test: a claim earns trust only when failure modes are shown across the",
    "# real input distribution at survivable cost. Here we just SURFACE the question to ask.",
    "claims = [",
    "    \"Our agent books a flight end-to-end in this demo video.\",",
    "    \"New model beats SOTA by 0.4 points on one benchmark.\",",
    "    \"Open-source repro reproduces the gain on three independent datasets.\",",
    "    \"It writes a whole app from one prompt (curated screenshot).\",",
    "]",
    "",
    "",
    "def demo_or_distribution(claim):",
    "    # We can't *decide* for you — we hand you the senior reflex: ask for failure modes",
    "    # across the distribution. Strong signals of 'distribution-deep' are independent",
    "    # repro + multiple datasets; of 'demo-deep' are 'video', 'screenshot', 'one benchmark'.",
    "    lc = claim.lower()",
    "    demo_smell = any(w in lc for w in (\"demo\", \"video\", \"screenshot\", \"one benchmark\"))",
    "    dist_smell = any(w in lc for w in (\"repro\", \"independent\", \"datasets\", \"three\"))",
    "    lean = \"distribution-deep\" if dist_smell and not demo_smell else \"demo-deep (ask: show me the failure modes)\"",
    "    return lean",
    "",
    "",
    "for c in claims:",
    "    print(f\"- {demo_or_distribution(c):48} | {c}\")",
))
cells.append(md(
    "**What you just saw.** The helper doesn't *know* the truth — it just routes every "
    "impressive claim to the same reflex: *show me the failure modes across the real "
    "distribution.* Most \"X is solved\" claims die in the demo→distribution gap. Your job "
    "isn't to be cynical; it's to make the claimant show the ugly inputs.",
))

# --- 49.2 sources + cadence ---
cells.append(md(
    "## Part 2 — Your tracking pipeline (§49.2)",
    "",
    "You **cannot** follow everything, and trying *is* the burnout vector. Build a small "
    "pipeline instead: **few, high-signal sources**, **batched** into one weekly slot, and "
    "**learn by building**. Fill in your own below — the rule is *few, not many*, and **prune "
    "anything noisy three weeks running**.",
))
cells.append(code(
    "# ✍️ FILL IN: 2-3 sources you actually trust. More than ~5 and you've rebuilt the firehose.",
    "# kind ∈ {newsletter, release-notes, practitioner}. Keep it small on purpose.",
    "sources = [",
    "    {\"name\": \"<curated newsletter>\",        \"kind\": \"newsletter\",    \"why_trusted\": \"<signal, not hype>\"},  # ✍️",
    "    {\"name\": \"<your stack's release notes>\", \"kind\": \"release-notes\", \"why_trusted\": \"<the tools you USE>\"},  # ✍️",
    "    {\"name\": \"<a practitioner you trust>\",   \"kind\": \"practitioner\",  \"why_trusted\": \"<judgment earned>\"},   # ✍️",
    "]",
    "",
    "# ✍️ FILL IN: ONE weekly batch slot. Not 'whenever' — a real day + time you'll defend.",
    "weekly_slot = {\"day\": \"<e.g. Friday>\", \"time\": \"<e.g. 15:00>\", \"duration_min\": 45}  # ✍️",
    "",
    "if len(sources) > 5:",
    "    print(f\"⚠️ {len(sources)} sources — that's a firehose, not a pipeline. Prune to ~3.\")",
    "else:",
    "    print(f\"{len(sources)} sources, batched {weekly_slot['day']} @ {weekly_slot['time']} \"",
    "          f\"for {weekly_slot['duration_min']} min. Good — few and scheduled.\")",
    "for s in sources:",
    "    print(f\"  - {s['kind']:14} {s['name']}  ({s['why_trusted']})\")",
))

cells.append(md(
    "### ⚠️ Pitfall — resume-driven adoption",
    "",
    "Beware **resume-driven adoption**: rewriting a working stack around each quarter's "
    "fashionable framework. Migration costs are real, the churn rate of agent tooling is "
    "brutal, and the patterns underneath (loops, tools, memory, evals) barely change between "
    "frameworks (§49.2). **Adopt only when something solves a problem you can name, on the "
    "strength of your own spike.** The gate below makes you name that problem out loud.",
))
cells.append(code(
    "# ✍️ FILL IN one thing you're tempted to adopt this quarter, then answer the gate.",
    "candidate = {",
    "    \"name\": \"<framework / tool you're eyeing>\",          # ✍️",
    "    \"problem_it_solves\": \"<name a REAL problem you have, or leave blank>\",  # ✍️ blank => no adopt",
    "    \"you_ran_a_spike\": False,   # ✍️ True only after a 2-hour build against YOUR problem",
    "    \"migration_cost_days\": None,  # ✍️ your honest estimate",
    "}",
    "",
    "",
    "def adoption_gate(c):",
    "    names_a_problem = bool(c[\"problem_it_solves\"].strip())",
    "    if names_a_problem and c[\"you_ran_a_spike\"]:",
    "        return \"ADOPT — names a real problem AND backed by your own spike.\"",
    "    if not names_a_problem:",
    "        return \"DROP — resume-driven: no named problem. The timeline being loud is not a reason.\"",
    "    return \"WAIT — run the 2-hour spike first; decide on YOUR evidence, not the hype.\"",
    "",
    "",
    "print(adoption_gate(candidate))",
))

# --- depreciation schedule ---
cells.append(md(
    "## Part 3 — The depreciation schedule (🧠 §49.2)",
    "",
    "Treat knowledge as a **depreciation schedule**. Fundamentals — distributed systems, "
    "architecture, evaluation discipline, security, the agent loop — depreciate over "
    "*decades*. Provider APIs and framework idioms depreciate in *months*. Invest your "
    "scarce deep-learning time in the slow layer; **look up** the fast layer on demand "
    "(models are excellent at telling you the current shape of an SDK).",
    "",
    "Sort *your* current learning topics into the two buckets. Anxiety about \"falling "
    "behind\" is almost always anxiety about the layer you should be **looking up**, not "
    "memorizing.",
))
cells.append(code(
    "# ✍️ FILL IN with YOUR topics. Seeded from the chapter; edit to match your stack.",
    "slow_depreciating = [   # invest deep time here — pays off for years",
    "    \"the agent loop (tools/memory/orchestration)\",",
    "    \"evaluation discipline\",",
    "    \"distributed systems & architecture\",",
    "    \"security & blast-radius control\",",
    "    # ✍️ add your own fundamentals",
    "]",
    "fast_churning = [       # look up on demand — don't memorize",
    "    \"this quarter's provider API surface\",",
    "    \"a specific framework's idioms\",",
    "    # ✍️ add the fast layers you keep re-learning",
    "]",
    "",
    "print(\"INVEST (slow-depreciating fundamentals):\")",
    "for t in slow_depreciating:",
    "    print(f\"   • {t}\")",
    "print(\"\\nLOOK UP (fast-churning layers — on demand):\")",
    "for t in fast_churning:",
    "    print(f\"   • {t}\")",
    "ratio = len(slow_depreciating) / max(1, len(slow_depreciating) + len(fast_churning))",
    "print(f\"\\nShare of your list that's durable: {ratio:.0%} \"",
    "      f\"({'healthy — deep time well spent' if ratio >= 0.5 else 'you may be memorizing the look-up layer'})\")",
))

# --- spike log + model-swap drill ---
cells.append(md(
    "## Part 4 — Spike log & the model-swap drill (#checklist)",
    "",
    "Two recurring self-audits from the chapter's closing checklist:",
    "",
    "- **Quarterly spike** — a two-hour build against a real problem from *your* work, with a "
    "decide/adopt/drop outcome. *One build teaches more than fifty threads of commentary.*",
    "- **Model-swap drill** — *would your current architecture survive a model swap next "
    "quarter at the cost of an afternoon?* If not, you're coupled too tightly to one model.",
))
cells.append(code(
    "# ✍️ FILL IN one row per quarterly spike. Outcome ∈ {adopt, drop, revisit}.",
    "spike_log = [",
    "    {\"quarter\": \"2026-Q2\", \"thing\": \"<what you spiked>\", \"hours\": 2,",
    "     \"real_problem\": \"<which of YOUR problems>\", \"outcome\": \"revisit\"},  # ✍️",
    "]",
    "",
    "# ✍️ The model-swap drill, scored honestly.",
    "model_swap_drill = {",
    "    \"model_pinned_in_one_place\": False,   # ✍️ True if a single config/env, not littered",
    "    \"prompts_provider_agnostic\": False,   # ✍️ True if not glued to one vendor's quirks",
    "    \"eval_set_catches_regressions\": False, # ✍️ True if a swap would be CAUGHT, not shipped blind",
    "}",
    "",
    "",
    "def survives_model_swap(d):",
    "    score = sum(bool(v) for v in d.values())",
    "    if score == len(d):",
    "        return \"YES — a model swap is an afternoon. Architecture is honest.\"",
    "    gaps = [k for k, v in d.items() if not v]",
    "    return \"NOT YET — fix: \" + \", \".join(gaps)",
    "",
    "",
    "for row in spike_log:",
    "    print(f\"  {row['quarter']}: {row['thing']} ({row['hours']}h) -> {row['outcome']}\")",
    "print(\"\\nModel-swap drill:\", survives_model_swap(model_swap_drill))",
))

# --- print the assembled plan ---
cells.append(md(
    "### 🔧 Print your staying-current plan",
    "",
    "Now the payoff: the cell echoes everything you filled in as one compact, "
    "**version-stamped** plan you can paste into your notes. It carries the chapter's rule "
    "right on the artifact — *re-check and prune rather than accumulate*.",
))
cells.append(code(
    "plan = {",
    "    \"generated\": str(TODAY),",
    "    \"version_stamp\": VERSION_STAMP,",
    "    \"sources\": sources,",
    "    \"weekly_batch\": weekly_slot,",
    "    \"depreciation\": {\"invest\": slow_depreciating, \"look_up\": fast_churning},",
    "    \"adoption_gate_result\": adoption_gate(candidate),",
    "    \"model_swap\": survives_model_swap(model_swap_drill),",
    "}",
    "print(json.dumps(plan, indent=2))",
    "print(\"\\n# ⚠️\", VERSION_STAMP)",
))

# --- optional live first-pass reader ---
cells.append(md(
    "### (Optional) Use an LLM as your first-pass reader",
    "",
    "The chapter's tip (§49.1): *use an LLM as your first-pass reader* — \"summarize the "
    "claim, the evidence, the baselines, and the stated limitations\" — and reserve **your** "
    "attention for judging whether the claim matters to your systems. This cell shows the "
    "shape. In **MOCK=1** (default) it returns a canned summary so the worksheet stays "
    "offline; set `COMPANION_MOCK=0` (with `ANTHROPIC_API_KEY`) to run it live on a real "
    "abstract. ⚠️ Reading *about* a paper is a fine substitute for most of them — the handful "
    "that change your architecture still deserve the full read.",
))
cells.append(code(
    "FIRST_PASS_PROMPT = (",
    "    \"Summarize this paper's CLAIM, the EVIDENCE, the BASELINES it compares against, \"",
    "    \"and the stated LIMITATIONS. Be terse. Do not editorialize.\"",
    ")",
    "abstract = \"<paste an abstract here>\"  # ✍️ only used when MOCK=0",
    "",
    "",
    "def first_pass_summary(abstract_text):",
    "    if MOCK:",
    "        # Canned, realistic shape — NO network, NO key. This is what a first pass yields.",
    "        return {",
    "            \"claim\": \"Method X improves agent task success on benchmark B.\",",
    "            \"evidence\": \"+3.1 pts on B; ablations in Table 2.\",",
    "            \"baselines\": \"Compared vs. a single prompted baseline (no tool-use variant).\",",
    "            \"limitations\": \"One benchmark; no independent repro; cost not reported.\",",
    "        }",
    "    from anthropic import Anthropic  # live path shape; see Ch 11",
    "    client = Anthropic()",
    "    msg = client.messages.create(",
    "        model=MODEL, max_tokens=400,",
    "        messages=[{\"role\": \"user\", \"content\": FIRST_PASS_PROMPT + \"\\n\\n\" + abstract_text}],",
    "    )",
    "    return msg.content[0].text",
    "",
    "",
    "summary = first_pass_summary(abstract)",
    "print(json.dumps(summary, indent=2) if isinstance(summary, dict) else summary)",
    "print(\"\\n-> now YOU judge: do the baselines look fair? does it pass the four filters above?\")",
))

# 6) Senior lens -----------------------------------------------------------------
cells.append(md(
    "## 🎯 Senior lens",
    "",
    "The meta-bet that wins regardless of which lab leads next year: **position yourself "
    "where judgment compounds.** Own the layers AI doesn't — *what* to build, *where* the "
    "boundaries go, what \"good\" means, what's allowed to be autonomous — and treat every new "
    "capability as a component to be **evaluated, sandboxed, and orchestrated** by systems you "
    "design (§49.3). Engineers who do that don't compete with the frontier; they get "
    "**leverage** from it. Notice that this worksheet is itself that move: it doesn't try to "
    "*know* the frontier, it builds a small **system** for querying it on your terms. "
    "Verification is becoming the scarce skill — when generation is cheap, knowing whether the "
    "output is *right* is what commands a salary.",
))

# 7) Recap -----------------------------------------------------------------------
cells.append(md(
    "## Recap",
    "",
    "- **Read papers in 20 minutes**: abstract → results/figures → limitations → method only "
    "if it survives. Then the **four filter questions**; the bar is *all four*.",
    "- The hype filter is **demo vs. distribution** — respond to any \"X is solved\" with *show "
    "me the failure modes*.",
    "- A pipeline beats a firehose: **few high-signal sources**, **one weekly batch slot**, "
    "**prune what's noisy three weeks running**, and **learn by building**.",
    "- Knowledge is a **depreciation schedule** — invest in slow fundamentals, **look up** the "
    "fast layer on demand.",
    "- Guard against **resume-driven adoption**; adopt only on a named problem + your own "
    "spike. Keep architecture **model-swap-able** in an afternoon.",
    "- ⚠️ This artifact is **version-stamped and prunable** — *re-check and delete rather than "
    "accumulate*.",
))

# 8) Exercises -------------------------------------------------------------------
cells.append(md(
    "## Exercises",
    "",
    "1. **Score a real paper.** Take a paper you saw hyped this week, fill in `paper_review` "
    "honestly, and run `score_paper`. 🔮 Predict its verdict before running — were you "
    "generous on the baseline question?",
    "2. **Prune to three.** If your `sources` list is longer than three, cut it to three and "
    "write one sentence on what you'll *stop* reading and why (the three-weeks-of-noise rule).",
    "3. **Find your coupling.** Set the `model_swap_drill` flags to your project's true state. "
    "For every `False`, write the smallest change that flips it to `True` in an afternoon.",
    "4. **Schedule it for real.** Turn `weekly_slot` into an actual recurring calendar block "
    "this week, and add a `spike_log` row planning your next quarterly two-hour spike — name "
    "the *real problem* it targets.",
))
cells.append(code(
    "# Exercise 1 — re-fill paper_review for a real paper, predict, then score_paper(...).",
))
cells.append(code(
    "# Exercise 2 — prune `sources` to 3; note what you'll STOP reading and why.",
))
cells.append(code(
    "# Exercise 3 — set the model_swap_drill flags truthfully; list the afternoon-sized fixes.",
))
cells.append(code(
    "# Exercise 4 — add a planned spike_log row (quarter, thing, real_problem, outcome).",
))

# 9) Next ------------------------------------------------------------------------
cells.append(md(
    "## Next",
    "",
    "- **Canonical companions:** the markdown twins of this worksheet live beside it — "
    "[`REFERENCE.md`](./REFERENCE.md) (the curated starting shelf + the four filter questions) "
    "and [`tracking-system.worksheet.md`](./tracking-system.worksheet.md) (this fill-in, in "
    "plain markdown). This notebook is the optional executable surface for the same prompts.",
    "- **Back to the book:** Ch 49's closing **#checklist** — keep this worksheet and that "
    "checklist as *one product* (§49).",
    "- **Capstone tie-in:** the **model-swap drill** is the audit that keeps the "
    "[`../../../capstone/`](../../../capstone/) architecture honest — a model is a swappable "
    "component, not a load-bearing wall.",
    "- **This is the end of the technical material.** Everything before it is the slow-"
    "depreciating layer; this chapter is how you keep the fast layer from owning you.",
))

# --- assemble + write ----------------------------------------------------------
nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUT.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", OUT, "with", len(cells), "cells")
