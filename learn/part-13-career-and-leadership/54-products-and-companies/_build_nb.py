"""One-shot generator for 54-01-24-month-roadmap-worksheet.ipynb.

Emits a valid nbformat-4 notebook with cleared outputs (outputs=[], execution_count=null).
Kept in-folder per task constraints; safe to delete after the .ipynb is generated.
"""
import json
import pathlib

NB = "54-01-24-month-roadmap-worksheet.ipynb"


_ID = [0]


def _next_id():
    _ID[0] += 1
    return f"cell{_ID[0]:02d}"


def md(*lines):
    return {"cell_type": "markdown", "id": _next_id(), "metadata": {},
            "source": list(lines)}


def code(*lines):
    return {
        "cell_type": "code",
        "id": _next_id(),
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": list(lines),
    }


def splitlines_keepends(text):
    """nbformat stores source as a list of lines, each (except last) ending in \\n."""
    parts = text.split("\n")
    out = [p + "\n" for p in parts[:-1]]
    if parts[-1] != "":
        out.append(parts[-1])
    elif not out:
        out = [""]
    return out


def M(text):
    return md(*splitlines_keepends(text))


def C(text):
    return code(*splitlines_keepends(text))


cells = []

# 1. Title + header --------------------------------------------------------
cells.append(M(
"""# Your next twenty-four months, committed: a fill-in worksheet

> \U0001F4D3 *Companion to* **Modern Agentic AI Engineer** *· Ch 54 §54.1–54.4 · type: worksheet*

*One-line promise:* turn the book's closing chapter — engineer→founder transfers, the validation sequence, the four moats, and the 24-month roadmap — into **your** dated plan, captured in cells you fill in and the notebook prints back as a committed artifact.

> ⚠️ **This is a worksheet, not a lab — and by design there is no notebook to \"run.\"** Ch 54 is about *judgment*: should this exist, will anyone pay, and what do *you* do with your next two years. None of that executes as code (see this chapter's `PLAN.md` for why a synthetic founder-simulator here would be theatre). The few code cells only echo **your** answers back as a structured, dated plan — fully offline, no API key, ever."""
))

# 2. Why this matters ------------------------------------------------------
cells.append(M(
"""## \U0001F9E0 Why this matters

This is the only chapter written about *you* specifically, and it lands at an unusual moment: the same force running through the whole book — AI making code cheap — cuts the cost of *starting* more than it cuts anything else. The constraint has moved from \"can you build it?\" to \"should this exist, and will anyone pay?\" — which is exactly the **judgment layer** this book trained. A startup is not a product; it is a *search process for a repeatable business, run under a deadline set by your runway* (§54.1). And a 24-month roadmap is not a wish — it is a **commitment device**, which is why the honest companion is something you *fill in and date*, not a kernel you execute. Fill it in once now; revisit it quarterly."""
))

# 3. Objectives + prereqs --------------------------------------------------
cells.append(M(
"""## Objectives & prereqs

**By the end you can:**
- Name the three engineer habits the chapter flags as **liabilities** when over-applied, and your personal *tell* for each (§54.1).
- Lay out a concrete, **dated 24-month roadmap** across the chapter's four phases — consolidate, become visibly senior, lead something, choose your ladder (§54.4).
- Pre-fill the **validation sequence** if the founder path tempts you — start from pain → sell before you build → wedge → evaluation-as-feature → ship to a few, deeply (§54.2).
- Run a **moat & unit-economics audit** against the four durable advantages, and self-audit against the closing §54 checklist (§54.3).

**Prereqs:** book Ch 54 read. The inputs this roadmap *consolidates* are the artifacts from **Ch 50–53** — your portfolio (Ch 50), architect-track decision-driving (Ch 51), interview playbook (Ch 52), and public reputation (Ch 53) — plus the **capstone** (Parts IV–XI). Bring *your own* current state; nothing here is invented for you.

**Cost:** none. Fully offline — no API key, no model call, no package beyond the stdlib. `MOCK=1` is the only mode that matters here."""
))

# 4. Setup -----------------------------------------------------------------
cells.append(M("## Setup"))

cells.append(C(
"""import json
import os
from datetime import date

from dotenv import load_dotenv

load_dotenv()  # reads a git-ignored .env if present; never hardcode keys

# MOCK=1 (the default) keeps this notebook 100% offline. A worksheet about career and
# founding direction has NOTHING to call live: every cell is your own judgment echoed
# back as a dated plan. MOCK exists only to honor the repo contract; no key is ever
# required, and there is no MOCK=0 network path in this notebook by design.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

# ✍️ FILL IN your real start year/month. Calibrate every milestone to this.
# The chapter is explicit: \"the sequence is the point, not the dates.\"
START_YEAR, START_MONTH = 2026, 7  # ✍️ your month-1
VERSION_STAMP = "roadmap is a living commitment — revisit quarterly; re-date, don't abandon"

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _add_months(offset):
    # pure-stdlib month math: month 1 == START, so offset is 1-based.
    total = (START_YEAR * 12 + (START_MONTH - 1)) + (offset - 1)
    return total // 12, total % 12  # (year, 0-based month index)


def window(start_month, end_month):
    \"\"\"Human label for a phase, e.g. 'Jul 2026 – Sep 2026'.\"\"\"
    ay, am = _add_months(start_month)
    by, bm = _add_months(end_month)
    return f"{_MONTHS[am]} {ay} – {_MONTHS[bm]} {by}"


print("MOCK =", MOCK, "| fully offline — this worksheet never calls a network")
print("Start:", f"{_MONTHS[START_MONTH - 1]} {START_YEAR}",
      "— every phase below is dated relative to this.")"""
))

# 5. Body ------------------------------------------------------------------

# Part 1: engineer -> founder transfers / liabilities
cells.append(M(
"""## Part 1 — Engineer → founder: what transfers, what becomes a liability (§54.1)

More transfers than startup mythology admits: systems thinking, decomposition, trade-off analysis under constraints, shipping discipline, debugging an opaque system from symptoms. What does **not** transfer is the *reward function* — engineering optimizes for correctness, elegance, robustness; **markets pay for a painful problem, solved well enough, put in front of the right people**. The danger is that the very habits that made you strong become liabilities when over-applied. The chapter names three. Below, name *your own tell* for each — the specific way it shows up in you."""
))

cells.append(C(
"""# The three engineer habits the chapter flags as liabilities, verbatim in intent (§54.1).
# ✍️ FILL IN your_tell: the concrete way this one bites YOU. Be specific and honest.
liabilities = [
    {"habit": "Perfection before contact",
     "founder_truth": "Ship when it can teach you something, not when it's right. "
                      "Quality matters — but only after you've proven anyone wants it.",
     "your_tell": "<e.g. I polish the eval harness before I've shown a single prospect>"},  # ✍️
    {"habit": "Building as the default verb",
     "founder_truth": "When anxious, the engineer writes code (code obeys). Usually the "
                      "company needed a sales conversation instead.",
     "your_tell": "<e.g. I refactor when I'm scared to send the cold email>"},  # ✍️
    {"habit": "Solving the interesting problem",
     "founder_truth": "Markets reward boring problems with budgets attached. The fascinating "
                      "architecture serving a problem nobody pays for is a hobby with a burn rate.",
     "your_tell": "<e.g. I reach for multi-agent before I've validated single-agent demand>"},  # ✍️
]

for L in liabilities:
    filled = not L["your_tell"].startswith("<")
    mark = "✓" if filled else "— (name your tell)"
    print(f"• {L['habit']:30} {mark}")
    print(f"    founder truth: {L['founder_truth']}")
    if filled:
        print(f"    your tell:     {L['your_tell']}")
    print()"""
))

# Part 2: the 24-month roadmap (the spine)
cells.append(M(
"""## Part 2 — The 24-month roadmap (the worksheet's spine, §54.4)

Here is the concrete plan. **Calibrate the timeline to your start (`START_YEAR`/`START_MONTH` above) — the sequence is the point, not the dates.** Four phases:

- **Months 1–3 — consolidate.** Finish the capstone to *operated*, not demoed: real users (even three), real traces, real cost dashboard, ADRs written. This single artifact powers everything after.
- **Months 4–9 — become visibly senior.** Claim one piece of next-level scope *in writing* with your manager (Ch 50). Ship one substantive public artifact per month in one niche (Ch 53). Build the eval-first reputation: be the person who shows numbers.
- **Months 10–15 — lead something.** Drive one cross-team initiative through the full **RFC → pre-wiring → decision → ADR** loop (Ch 51). Mentor someone deliberately. If job-searching, run the Ch 52 playbook in parallel processes, *at* the level your portfolio proves.
- **Months 16–24 — choose your ladder.** **Path A:** convert the record into a staff/architect role. **Path B:** take the painful workflow you keep noticing and run the validation sequence. A real, *chosen* decision — not drift.

Fill in one concrete, dated commitment per phase."""
))

cells.append(C(
"""# ✍️ FILL IN: one concrete, measurable commitment per phase. 'commitment' should be a
# thing you could show someone, not a vibe. The dates auto-compute from START.
roadmap = [
    {"phase": "consolidate",            "months": (1, 3),
     "goal": "Capstone -> OPERATED: real users, traces, cost dashboard, ADRs.",
     "commitment": "<e.g. 3 real users on the capstone + a cost dashboard by month 3>"},  # ✍️
    {"phase": "become visibly senior",  "months": (4, 9),
     "goal": "Next-level scope in writing (Ch50) + 1 public artifact/month (Ch53).",
     "commitment": "<e.g. scope doc agreed w/ manager; 6 posts in my niche>"},  # ✍️
    {"phase": "lead something",         "months": (10, 15),
     "goal": "One cross-team RFC -> pre-wiring -> decision -> ADR (Ch51); mentor one person.",
     "commitment": "<e.g. drive the retrieval-platform RFC to a signed ADR>"},  # ✍️
    {"phase": "choose your ladder",     "months": (16, 24),
     "goal": "Path A (staff/architect role) OR Path B (validate the painful workflow).",
     "commitment": "<e.g. CHOSEN: Path B — run validation on the X workflow>"},  # ✍️
]

print("YOUR 24-MONTH ROADMAP")
print("=" * 60)
for r in roadmap:
    lo, hi = r["months"]
    filled = not r["commitment"].startswith("<")
    mark = "✓" if filled else "— fill in"
    print(f"Months {lo:>2}–{hi:<2}  ({window(lo, hi)})  [{mark}]")
    print(f"  goal:       {r['goal']}")
    print(f"  commitment: {r['commitment']}")
    print()"""
))

# Predict prompt
cells.append(M(
"""### \U0001F52E Predict — your honest biggest uncertainty for Path B

Before running the next cell, **write down** what you believe is the single biggest uncertainty standing between you and a viable product. Most engineers reflexively answer *\"can we build it?\"* — the chapter insists that is almost never it. The real uncertainty is **\"will they pay, and can we reach them?\"** Predict your own answer, then see whether the helper agrees with where your iterations should go."""
))

cells.append(C(
"""# ✍️ FILL IN your honest biggest uncertainty for the founder path, in your words.
biggest_uncertainty = "<the one thing you're least sure of about Path B>"  # ✍️


def where_to_spend_iterations(text):
    # The chapter's claim: for an engineer-founder the biggest uncertainty is almost never
    # 'can we build it'. If your stated uncertainty is build/tech-shaped, the helper redirects
    # you to the market question — because that's where the cheap, decisive experiments live.
    lc = text.lower()
    build_smell = any(w in lc for w in
                      ("build", "scale", "architecture", "model", "latency", "infra", "code"))
    market_smell = any(w in lc for w in
                       ("pay", "reach", "customer", "demand", "willing", "channel", "distribution"))
    if market_smell and not build_smell:
        return ("On target — spend iterations on demand & distribution. "
                "Design the cheapest experiment that reduces it.")
    if build_smell and not market_smell:
        return ("⚠️ Build-shaped uncertainty. Re-read §54.1: it's almost never 'can we build it'. "
                "Reframe toward 'will they pay, can we reach them' — that's the expensive unknown.")
    return ("Make it sharper — a good uncertainty names a person, a payment, and a channel, "
            "so you can run a 2-week experiment against it.")


print("Your stated uncertainty:")
print(" ", biggest_uncertainty)
print()
print("Where to spend iterations:")
print(" ", where_to_spend_iterations(biggest_uncertainty))"""
))

cells.append(M(
"""**What you just saw.** The helper can't know your market — it just routes you to the senior reflex from §54.1: the biggest uncertainty for an engineer-founder is *demand and distribution*, not feasibility. If your gut answer was build-shaped, that's the tell — the engineer optimizing the part that obeys. The next section turns the right uncertainty into a cheap experiment."""
))

# Part 3: validation sequence
cells.append(M(
"""## Part 3 — The validation sequence (Path B pre-fill, §54.2)

The failure mode of technical founders is validating the *technology* (\"the agent works!\") instead of the *business* (\"someone pays, repeatedly, and tells their peers\"). The sequence that guards against it — in order, no skipping:

1. **Start from pain, not capability.** Not \"what can agents do?\" but \"what does this specific role spend *tedious, budgeted* hours on?\"
2. **Sell before you build.** ~20 prospect conversations + a concierge/mockup + an ask with teeth (a paid pilot or a signed LOI). Polite interest is noise; *money committed* is signal. Two weeks here can save two years.
3. **Build the wedge, not the platform.** One painful workflow done excellently — explainable in a sentence, deliverable by a tiny team, expandable later.
4. **Make evaluation a product feature.** The Part VI eval harness becomes your sales deck: *here is our measured accuracy on your data, and the dashboard you'll watch it on.* Trust is the product; the agent is the mechanism.
5. **Ship to a few, deeply.** Five customers you talk to weekly beat five hundred sign-ups you don't. Early on you are *searching*, not scaling."""
))

cells.append(C(
"""# ✍️ FILL IN the validation sequence for ONE candidate idea. Leave it as the placeholder
# if you're on Path A — the gate below will simply say 'Path A: validation not engaged'.
validation = [
    {"step": "start from pain",     "done": False,
     "evidence": "<which role, which tedious BUDGETED hours>"},                 # ✍️
    {"step": "sell before build",   "done": False,
     "evidence": "<#prospect convos; the ask-with-teeth: paid pilot or signed LOI>"},  # ✍️
    {"step": "wedge not platform",  "done": False,
     "evidence": "<the one workflow, explainable in a sentence>"},             # ✍️
    {"step": "eval as a feature",   "done": False,
     "evidence": "<measured accuracy on THEIR data + the dashboard you'd show>"},  # ✍️
    {"step": "ship to a few deeply", "done": False,
     "evidence": "<the 3–5 design partners you talk to weekly>"},               # ✍️
]


def validation_status(steps):
    # The sequence is ordered: you can't honestly claim step N done while N-1 is open.
    # Report the first incomplete step — that's the one experiment to run next.
    for i, s in enumerate(steps, 1):
        if not s["done"]:
            return f"NEXT EXPERIMENT → step {i}: {s['step']} ({s['evidence']})"
    return "All five validated — you're past search; now scale the depth, not the logo count."


engaged = any(not s["evidence"].startswith("<") for s in validation)
if not engaged:
    print("Path A (or not yet engaged): validation sequence is here when you want it.")
else:
    print(validation_status(validation))
    for i, s in enumerate(validation, 1):
        box = "✓" if s["done"] else " "
        print(f"  [{box}] {i}. {s['step']:18} {s['evidence']}")"""
))

# Pitfall
cells.append(M(
"""### ⚠️ Pitfall — the demo trap at company scale

The demo trap from Chapter 1 returns at *company* scale, with **investors** playing the impressed audience. Agentic demos are spectacularly convincing — a fundraise can run **ahead of** a product that still fails on every hard input. The gap between the polished demo and the *dependable system* **is the company**: everything the book taught about reliability, evals, and operations is what you are actually selling. The check below makes you confront that gap in numbers, not vibes."""
))

cells.append(C(
"""# ✍️ FILL IN honestly. The demo trap is believing the demo IS the product.
demo_vs_dependable = {
    "demo_input_success_rate": None,   # ✍️ e.g. 0.98 on the inputs you choose for the video
    "hard_input_success_rate": None,   # ✍️ e.g. 0.61 on the ugly real distribution
    "raising_ahead_of_reliability": None,  # ✍️ True if pitch/fundraise outruns measured reliability
}


def demo_trap_check(d):
    demo, hard = d["demo_input_success_rate"], d["hard_input_success_rate"]
    if demo is None or hard is None:
        return "Fill in both rates — the GAP between them is the engineering you must still ship."
    gap = demo - hard
    warn = " ⚠️ raising ahead of reliability" if d.get("raising_ahead_of_reliability") else ""
    verdict = ("company-sized gap: this gap IS the product" if gap >= 0.15
               else "narrow gap — the dependable system is close")
    return f"demo {demo:.0%} vs hard {hard:.0%} → gap {gap:.0%}: {verdict}{warn}"


print(demo_trap_check(demo_vs_dependable))"""
))

# Part 4: moats & economics
cells.append(M(
"""## Part 4 — Moat & unit-economics audit (\U0001F9E0 §54.3)

Two structural questions decide whether your product is a *business* or a *feature awaiting absorption*: **why won't this be commoditized?** and **do the unit economics work?**

The **model itself is not a moat** — whatever frontier capability you rent, competitors rent too, and each release lifts every boat. \"Thin wrapper\" is the correct slur. The four durable advantages accumulate *around* the model:

1. **Workflow depth & integration** — woven into systems, permissions, processes; expensive to rip out.
2. **Proprietary data & feedback loops** — every correction/escalation/outcome improves your evals, routing, fine-tuning; design the product to generate this exhaust from day one.
3. **Trust, compliance & track record** — audited security, certifications, a year of measured accuracy. Slow to build — which is what makes it a moat.
4. **Distribution** — the audience, community, and reputation of Ch 53.

**Economics:** every request burns real compute, so gross margin is an *engineering output*, not a spreadsheet line. Token cost, **model routing** (cheap model for triage, frontier for the hard 10%), caching, and context discipline translate into margin. Price on **value delivered** (per resolution/task/outcome), and model the **trend line** — capability-per-dollar keeps falling — not today's snapshot."""
))

cells.append(C(
"""# ✍️ FILL IN: rate YOUR idea 0–5 on each durable advantage (0 = none, 5 = strong & proven).
moats = {
    "workflow_depth_integration": 0,        # ✍️ woven into their systems/permissions/process?
    "proprietary_data_feedback_loops": 0,   # ✍️ does usage generate compounding exhaust?
    "trust_compliance_track_record": 0,     # ✍️ audited security / certs / measured accuracy?
    "distribution": 0,                      # ✍️ audience/community/reputation to reach buyers?
}


def moat_audit(m):
    total = sum(m.values())
    weakest = min(m, key=m.get)
    if total == 0:
        return "No moat rated yet — a 0/20 idea is a thin wrapper until proven otherwise."
    health = ("defensible-in-progress" if total >= 10 else
              "thin — a single model release could absorb you")
    return f"moat score {total}/20 ({health}); invest first in your weakest: {weakest}"


print(moat_audit(moats))"""
))

cells.append(C(
"""# ✍️ FILL IN a back-of-envelope unit economy for ONE unit of value (a resolution/task).
# All offline arithmetic — numbers are yours to set. This models the TREND, not gospel.
unit = {
    "price_per_outcome_usd": 0.0,     # ✍️ value-based price for ONE resolution/task/outcome
    "triage_calls": 0,                # ✍️ cheap-model calls for the easy 90%
    "triage_cost_usd": 0.0,           # ✍️ cost of one cheap-model call
    "frontier_calls": 0,              # ✍️ frontier-model calls for the hard 10%
    "frontier_cost_usd": 0.0,         # ✍️ cost of one frontier call
    "cache_hit_rate": 0.0,            # ✍️ 0–1; caching cuts repeated context cost
}


def gross_margin(u):
    raw = (u["triage_calls"] * u["triage_cost_usd"]
           + u["frontier_calls"] * u["frontier_cost_usd"])
    cogs = raw * (1 - u["cache_hit_rate"])  # caching trims the marginal compute
    price = u["price_per_outcome_usd"]
    if price <= 0:
        return "Set a value-based price > 0 — don't race to per-seat parity with $0-marginal SaaS."
    margin = (price - cogs) / price
    note = ("healthy — and the trend line improves it (capability/$ keeps falling)"
            if margin >= 0.6 else
            "thin today — route harder (cheap triage), cache more, or raise on value")
    return f"COGS ${cogs:.4f} on price ${price:.2f} → gross margin {margin:.0%} ({note})"


print(gross_margin(unit))"""
))

# 6. Senior lens -----------------------------------------------------------
cells.append(M(
"""## \U0001F3AF Senior lens

One last time, the through-thesis the book has carried since Chapter 1: **AI writes the code; humans own the judgment** — what to build, where the boundaries go, which trade-offs fit, whether the system can be trusted. *Every move on your roadmap invests in the judgment layer* — the one asset no model release devalues. And notice the punchline of §54.3: **in agentic AI, the moat *is* the engineering this book taught.** Anyone can call the model; few can deliver measured reliability, bounded cost, integrated workflows, and a feedback loop that compounds — and fewer still can *prove* it to a buyer. The unglamorous production chapters were never overhead on the idea; they are the defensible part of the company. Whether you pick Path A or Path B, you are spending the same asset: judgment, made visible, compounding."""
))

# 7. Recap -----------------------------------------------------------------
cells.append(M(
"""## Recap

- A startup is a **search process for a repeatable business under a runway deadline** — not a product. The reward function isn't the engineer's; markets pay for *painful problems solved well enough, put in front of the right people*.
- Three engineer habits turn into liabilities: **perfection before contact**, **building as the default verb**, **solving the interesting problem**. Know your tell for each.
- The validation sequence is ordered: **start from pain → sell before you build → wedge not platform → evaluation as a feature → ship to a few, deeply.** *Money committed* is the only real signal.
- ⚠️ The **demo trap** scales to investors; the gap between demo and dependable system **is the company**.
- Four durable moats — **workflow depth, proprietary data + feedback loops, trust/compliance/track record, distribution** — and economics where **margin is an engineering output** (routing, caching, value-based pricing, modeling the trend line).
- The roadmap's four phases — **consolidate → become visibly senior → lead something → choose your ladder** — each invest in the judgment layer. The moat *is* the engineering."""
))

# 8. Exercises -------------------------------------------------------------
cells.append(M(
"""## Exercises

1. **Date the whole spine.** Set `START_YEAR`/`START_MONTH` to your real start month, fill one *measurable* `commitment` per phase, and re-run. \U0001F52E Predict which phase you're most likely to let slip — then write the one guardrail that protects it.
2. **Run the validation gate.** If Path B tempts you, fill in `validation` honestly and find your `validation_status` next-step. Design the **cheapest 2-week experiment** that reduces your `biggest_uncertainty`, and write it down.
3. **Audit the moat, then the math.** Score `moats` 0–5 each and fill in `unit`. For your *weakest* moat, write the smallest move that raises it one point; for the economics, find the one lever (routing, caching, or price) that most improves `gross_margin`.
4. **Self-audit against the §54 checklist (next cell).** Mark each box truthfully and write the single next action for every `False`."""
))

cells.append(C(
"""# Exercise 1 — re-date the roadmap (set START_YEAR/START_MONTH), fill commitments, re-run Part 2."""
))
cells.append(C(
"""# Exercise 2 — fill `validation`; write the cheapest 2-week experiment for your uncertainty."""
))
cells.append(C(
"""# Exercise 3 — score `moats` and `unit`; name the one lever that most improves margin."""
))
cells.append(C(
"""# Exercise 4 — the §54 checklist as a self-audit. Mark each True only if it's genuinely done.
checklist = {
    "one_system_operated_and_written_up": False,   # finished, operated, measured, ADRs — proof of work
    "one_next_level_scope_in_writing":    False,   # responsibility claimed at work, agreed in writing (Ch50)
    "one_monthly_public_channel":         False,   # an artifact shipped every month, one niche (Ch53)
    "one_community_where_known":          False,   # a project/group where your help is felt (Ch53)
    "one_rfc_to_adr_initiative":          False,   # a cross-team decision you drove (Ch51)
    "one_chosen_decision_at_month_24":    False,   # climb the ladder you're on OR build your own — chosen
}

done = sum(checklist.values())
print(f"§54 self-audit: {done}/{len(checklist)} done")
for k, v in checklist.items():
    print(f"  [{'✓' if v else ' '}] {k}")
    if not v:
        print("        next action: <✍️ smallest concrete step to flip this True>")"""
))

# Optional: print-the-plan artifact
cells.append(M(
"""### \U0001F527 Print your committed plan

The payoff: this cell echoes everything you filled in as one compact, **dated, version-stamped** artifact you can paste into your notes (or an ADR, per `templates/adr-template/`). It carries the chapter's rule on its face — *revisit quarterly; re-date, don't abandon.*"""
))

cells.append(C(
"""committed_plan = {
    "start": f"{_MONTHS[START_MONTH - 1]} {START_YEAR}",
    "version_stamp": VERSION_STAMP,
    "liabilities_owned": [
        {"habit": L["habit"], "your_tell": L["your_tell"]}
        for L in liabilities if not L["your_tell"].startswith("<")
    ],
    "roadmap": [
        {"phase": r["phase"], "window": window(*r["months"]), "commitment": r["commitment"]}
        for r in roadmap
    ],
    "biggest_uncertainty": biggest_uncertainty,
    "validation_next": (validation_status(validation) if engaged
                        else "Path A — validation sequence not engaged"),
    "moat_audit": moat_audit(moats),
    "unit_economics": gross_margin(unit),
}
print(json.dumps(committed_plan, indent=2))
print()
print("# ⚠️", VERSION_STAMP)"""
))

# 9. Next ------------------------------------------------------------------
cells.append(M(
"""## Next

- **This is the last page of the book.** There is no next chapter — there is your roadmap. The \"Months 1–3: consolidate\" milestone *is* finishing the [`../../../capstone/`](../../../capstone/) to **operated** (real users, traces, cost dashboard, ADRs); that one artifact, once operated, becomes either your architect-track proof (Path A) or the technical core of the product (Path B).
- **Record founding decisions as ADRs:** use [`../../../templates/adr-template/`](../../../templates/adr-template/) for model-agnostic boundaries and the routing you control, and [`../../../templates/system-design-doc/`](../../../templates/system-design-doc/) for the moat/economics trade-off discipline behind a wedge.
- **Inputs this roadmap consolidates:** the worksheets and artifacts from **Ch 50–53** — portfolio, next-level scope, public cadence, the RFC→ADR loop — are what the four phases above pull together.
- **Back to the book:** keep this worksheet and the closing **§54 #checklist** as *one product*. The models will keep improving — good; every improvement makes your hands faster and your judgment more valuable. Finish the capstone, claim the bigger scope, have the twenty conversations."""
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

out = pathlib.Path(__file__).parent / NB
out.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", out)
