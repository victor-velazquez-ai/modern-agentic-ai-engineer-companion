"""Generator for 47-02-grounding-and-task-success.ipynb.

Produces a valid nbformat-4 notebook with cleared outputs and null
execution_count. Run once, then this helper is deleted.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "47-02-grounding-and-task-success.ipynb")


def md(text):
    lines = text.split("\n")
    src = [l + "\n" for l in lines[:-1]] + ([lines[-1]] if lines[-1] else [])
    return {"cell_type": "markdown", "metadata": {}, "source": src}


def code(text):
    lines = text.split("\n")
    src = [l + "\n" for l in lines[:-1]] + ([lines[-1]] if lines[-1] else [])
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": src,
    }


cells = []

# 1. Title + header -----------------------------------------------------------
cells.append(md(
"""# The grounding ladder + a frozen success harness

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 47 §47.3 · type: concept-lab (with a grounding-ladder drill)*

**The promise:** by the end you can raise a computer-use agent's *per-step* reliability by grounding on **structure** (DOM / accessibility tree / set-of-marks) instead of pixels, verify each action against the world's real end-state, and **measure** whole-task success on a frozen suite — then prove a config change helped or regressed with a number, not a vibe.

Fully offline: a mock DOM, a set-of-marks overlay, and programmatic end-state checkers. No model and no network are needed for the grounding mechanics — that's the point."""
))

# 2. Why this matters ---------------------------------------------------------
cells.append(md(
"""## 🧠 Why this matters

From 47-01 you know the harness keeps a confused agent *safe*. Reliability keeps it from getting confused in the first place — and per-step accuracy is the lever that matters most, because it **compounds** over a long flow (0.98²⁰ ≈ 0.67).

Most of that lever is in how the agent **grounds**: what it perceives and how it references a target. A model clicking raw pixel `(840, 612)` is guessing at geometry — one layout shift and it clicks the wrong thing. Grounding on the **DOM** / **accessibility tree** gives it the real interactive elements with stable ids, so it targets *the submit button*, not *a pixel*. **Set-of-marks** joins the two worlds: overlay numbered labels on the interactive elements and let the model act by *id* ("click element 7"). Then you **verify each action** against the end-state and **measure** task-success on a frozen suite. See §47.3."""
))

# 3. Objectives + prereqs -----------------------------------------------------
cells.append(md(
"""## Objectives & prereqs

**By the end you can:**
- Rank grounding strategies on **the grounding ladder**: real API → DOM/accessibility actions → set-of-marks → raw pixels.
- Build a **set-of-marks** overlay from a mock DOM (numbered interactive elements) and act by *id*.
- Show a **pixel** click missing after a simulated layout shift while the **set-of-marks id** still resolves.
- Add **verify-and-replan**: after each action, assert the world changed (URL / element / value) and replan on mismatch.
- Run a **frozen task-success harness** — fixed tasks + programmatic *end-state* checks — and compare two configs (pixels vs set-of-marks) by success rate.

**Prereqs:** `47-01` (the sandboxed loop & harness) · Ch 22 (evaluation harnesses; golden / fixed suites — same discipline).

**Packages:** the standard library only (`os`, `json`, `random`, `dataclasses`, `pathlib`) plus `python-dotenv`. Fixtures load from `data/`."""
))

# 4. Setup --------------------------------------------------------------------
cells.append(code(
'''# --- Setup -------------------------------------------------------------------
import json
import os
import random
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads a local .env if present; never hardcode keys

# MOCK=1 (default): everything here is deterministic, offline mechanics -- a mock
# DOM, a set-of-marks overlay, and programmatic end-state checkers. NO model is
# required for the grounding lesson. An optional mocked-model config drives the
# suite below; there is no live API path in this notebook.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(47)  # determinism for the suite's mocked agent

DATA = Path("data")
print(f"MOCK mode: {MOCK}  (offline; mock DOM + programmatic checkers)")
print("fixtures dir exists:", DATA.exists(), "->", sorted(p.name for p in DATA.glob('*')))'''
))

# 5a. The grounding ladder drill ---------------------------------------------
cells.append(md(
"""## 1 · The grounding ladder (a tiny drill)

Before any code, fix the mental model. When an agent needs to *reference a target*, prefer the most structured signal a surface offers, in this order:

| Rung | Strategy | Why it's higher |
|---|---|---|
| 1 (best) | **Real API** | No screen at all — deterministic, testable |
| 2 | **DOM / accessibility-tree actions** | Real elements, roles, stable ids |
| 3 | **Set-of-marks** over a screenshot | Visual context + a discrete id the harness resolves exactly |
| 4 (worst) | **Raw pixel coordinates** | Pure geometry; breaks on any layout shift |

Drill: given a surface, name the *highest available* rung."""
))

cells.append(code(
'''# Drill: pick the highest rung available for each surface. The ranking is fixed:
# real_api(4) > dom(3) > set_of_marks(2) > pixels(1). Higher == more reliable.
LADDER = {"real_api": 4, "dom": 3, "set_of_marks": 2, "pixels": 1}


def best_grounding(available: list[str]) -> str:
    """Return the most-structured grounding strategy that's available."""
    return max(available, key=lambda s: LADDER[s])


cases = {
    "internal service with REST API": ["real_api", "dom", "set_of_marks", "pixels"],
    "standard web form (no API)":     ["dom", "set_of_marks", "pixels"],
    "canvas/embedded video widget":   ["pixels"],          # nothing structured exposed
    "native desktop app (a11y tree)": ["dom", "set_of_marks", "pixels"],
}
for surface, avail in cases.items():
    print(f"{surface:34s} -> use {best_grounding(avail)!r}")'''
))

cells.append(md(
"""**What you just saw.** The rule is mechanical: take the highest rung the surface exposes. A real API beats everything; pixels are the fallback of last resort — *only* the canvas/video widget, which exposes no structure, is forced down to them. Every step up that ladder buys per-step reliability, which compounds over a long task into the whole game."""
))

# 5b. Mock DOM + set-of-marks -------------------------------------------------
cells.append(md(
"""## 2 · Build a set-of-marks overlay from a mock DOM

A real set-of-marks layer reads the DOM (or accessibility tree), finds the interactive elements, and stamps a numbered label on each. We do exactly that over a small mock DOM loaded from `data/mock_dom.json`. Each interactive element gets a stable **id** *and* a current pixel **box** (so we can contrast the two grounding styles)."""
))

cells.append(code(
'''# Load the mock DOM fixture: a list of nodes, each with a role, label, stable id,
# and a pixel bounding box [x, y, w, h] for the CURRENT layout.
dom = json.loads((DATA / "mock_dom.json").read_text(encoding="utf-8"))
interactive = [n for n in dom["nodes"] if n["interactive"]]

print(f"page: {dom['url']}  ({len(dom['nodes'])} nodes, {len(interactive)} interactive)\\n")


def set_of_marks(nodes: list[dict]) -> dict[int, dict]:
    """Assign a numbered mark to each interactive element (the overlay)."""
    return {i: node for i, node in enumerate(nodes, start=1)}


marks = set_of_marks(interactive)
print("set-of-marks overlay (act by these ids):")
for mark_id, node in marks.items():
    print(f"  [{mark_id}] {node['role']:8s} {node['label']!r:24s} id={node['id']!r}")'''
))

# 5c. Predict: pixel vs set-of-marks after layout shift -----------------------
cells.append(md(
"""## 3 · 🔮 Predict: a pixel click vs a set-of-marks id after a layout shift

Here's the crux. Two ways to "click the **Add to cart** button":
- **Pixel grounding:** remember its box from the first render and click the center coordinate.
- **Set-of-marks grounding:** remember its **mark id** and let the harness resolve the id to *whatever box it has now*.

Then the page **re-renders with a layout shift** (a banner pushes everything down 40px). We replay both the remembered pixel coordinate and the remembered mark id against the new layout.

**Predict before running:**
1. After the shift, does the remembered **pixel** coordinate still land on "Add to cart"? On *what*, if not?
2. Does the remembered **mark id** still resolve to the right element?"""
))

cells.append(code(
'''def center(box):
    x, y, w, h = box
    return (x + w // 2, y + h // 2)


def hit_test(nodes, point):
    """Which element (if any) contains this pixel? (what a pixel click 'hits')."""
    px, py = point
    for n in nodes:
        x, y, w, h = n["box"]
        if x <= px <= x + w and y <= py <= y + h:
            return n
    return None


# Target: the 'Add to cart' button. Capture how each grounding strategy refers to it.
add_btn = next(n for n in interactive if n["id"] == "add")
remembered_pixel = center(add_btn["box"])        # pixel grounding: a coordinate
remembered_mark = next(i for i, n in marks.items() if n["id"] == "add")  # SoM: an id
print(f"target 'Add to cart': remembered pixel={remembered_pixel}, mark id=[{remembered_mark}]")

# --- The layout shifts: a banner pushes every element DOWN by 40px. ----------
shifted = json.loads((DATA / "mock_dom.json").read_text(encoding="utf-8"))
for n in shifted["nodes"]:
    x, y, w, h = n["box"]
    n["box"] = [x, y + 40, w, h]          # everything moved; ids are unchanged
shifted_interactive = [n for n in shifted["nodes"] if n["interactive"]]
shifted_marks = set_of_marks(shifted_interactive)

# Pixel grounding: replay the OLD coordinate against the NEW layout.
pixel_hit = hit_test(shifted["nodes"], remembered_pixel)
# Set-of-marks grounding: the id still names the same element, new box and all.
som_hit = shifted_marks[remembered_mark]

# Resolve the pixel hit to a label BEFORE the f-string (a ternary can't follow !r).
pixel_label = repr(pixel_hit["label"]) if pixel_hit else "NOTHING / wrong element"

print("\\nafter a 40px layout shift:")
print(f"  pixel  ({remembered_pixel}) now hits -> {pixel_label}")
print(f"  mark   [{remembered_mark}]   still resolves -> {som_hit['label']!r} (id={som_hit['id']!r})")'''
))

cells.append(md(
"""**What you just saw.** The remembered pixel coordinate now lands on the *wrong* element (or empty space) — the geometry moved out from under it. The **mark id** resolved to the same "Add to cart" button regardless of where it rendered, because it references *structure*, not *position*. This is set-of-marks' whole value: the model still gets visual context to reason over, but it commits to a discrete target the harness can resolve exactly."""
))

# 5d. Verify-and-replan -------------------------------------------------------
cells.append(md(
"""## 4 · Verify each action, then replan on mismatch

Grounding gets you a better *aim*; verification keeps a misfire from compounding. After **every** action, assert the world changed as expected — URL changed, expected element appeared, value actually filled — and if not, **replan** instead of barreling ahead on a stale model. This is the per-step embodiment of the harness-verified checkpoints from 47-01's compounding-reliability pitfall."""
))

cells.append(code(
'''@dataclass
class MockWorld:
    """A tiny structured world the agent acts on (no pixels needed here)."""
    url: str = "https://shop.sandbox.test/search"
    cart: list = field(default_factory=list)

    def click(self, element_id: str) -> None:
        if element_id == "add":
            self.cart.append("Wireless Mouse")
            self.url = "https://shop.sandbox.test/checkout"


def act_and_verify(world: MockWorld, element_id: str, expect: dict) -> dict:
    """Do one action, then VERIFY the end-state matches `expect`. Replan if not."""
    before = {"url": world.url, "cart_len": len(world.cart)}
    world.click(element_id)
    after = {"url": world.url, "cart_len": len(world.cart)}

    ok = all(
        (after.get("url") == v if k == "url" else after.get("cart_len") == v)
        for k, v in expect.items()
    )
    return {"ok": ok, "before": before, "after": after,
            "decision": "continue" if ok else "REPLAN (world did not change as expected)"}


# Correct action: clicking 'add' should land us on checkout with 1 item.
w = MockWorld()
good = act_and_verify(w, "add", expect={"url": "https://shop.sandbox.test/checkout", "cart_len": 1})
print("verified action:", json.dumps(good, indent=2))

# A stale/wrong action: clicking a non-existent 'add2' changes nothing -> replan.
w2 = MockWorld()
bad = act_and_verify(w2, "add2", expect={"cart_len": 1})
print("\\nunverified action ->", bad["decision"])'''
))

cells.append(md(
"""**What you just saw.** The verified action confirms the cart grew and the URL advanced, so the loop continues. The bad action changed nothing — and instead of *assuming* it worked (the failure mode that turns one misclick into a ten-step detour), the harness flags `REPLAN`. Verification is cheap; a stale mental model is expensive."""
))

# 5e. Frozen success harness --------------------------------------------------
cells.append(md(
"""## 5 · A frozen task-success harness (the number that matters)

Spot-checking a computer-use agent by hand doesn't scale and misses regressions when you swap a model or tweak a prompt. So we do what the field standardizes on (WebArena / OSWorld mold): a **frozen** set of tasks in a reproducible environment, with a **programmatic checker** that inspects the *end state* — was the item actually in the cart? — not whether the agent *narrated* success.

We load a frozen suite from `data/task_suite.json` and run two configs through it:
- `pixels` — grounding that **degrades after a layout shift** (modeled as a per-step success probability).
- `set_of_marks` — structure-grounded, robust to the shift.

The checker reads end-state only. Same tasks, same seed; only the grounding changes."""
))

cells.append(code(
'''suite = json.loads((DATA / "task_suite.json").read_text(encoding="utf-8"))
print(f"frozen suite '{suite['name']}' — {suite['as_of']} — {len(suite['tasks'])} tasks\\n")

# Per-step reliability by config (the LESSON: structure > pixels). These stand in
# for "how often a step lands correctly" under each grounding style on this suite.
PER_STEP = {"pixels": 0.85, "set_of_marks": 0.97}


def run_task(task: dict, config: str, rng: random.Random) -> bool:
    """Mocked agent: succeeds a step with PER_STEP[config] prob; task needs ALL steps.

    Then a PROGRAMMATIC end-state check decides pass/fail -- not the agent's say-so.
    """
    p = PER_STEP[config]
    all_steps_ok = all(rng.random() < p for _ in range(task["steps"]))
    # End-state checker: the cart must contain exactly the expected item set.
    final_cart = set(task["expected_cart"]) if all_steps_ok else set()
    return final_cart == set(task["expected_cart"])  # programmatic, end-state only


def measure(config: str, trials: int = 200) -> float:
    rng = random.Random(47)  # frozen seed -> reproducible success rate
    passes = sum(
        run_task(task, config, rng)
        for _ in range(trials)
        for task in suite["tasks"]
    )
    return passes / (trials * len(suite["tasks"]))


print("running the frozen suite (200 trials x tasks) for each config...")'''
))

cells.append(md(
"""## 5b · 🔮 Predict: which config wins, and by how much?

Each task is multi-step, and a task only passes if **every** step lands (compounding again). `pixels` lands a step 85% of the time; `set_of_marks`, 97%.

**Predict before running:**
1. Roughly what whole-task success rate will `pixels` get? And `set_of_marks`?
2. Will the gap be *larger* or *smaller* than the 12-point per-step gap (97% − 85%)? (Think about what compounding does to the gap.)"""
))

cells.append(code(
'''rates = {cfg: measure(cfg) for cfg in PER_STEP}
for cfg, rate in rates.items():
    print(f"  {cfg:14s}: task-success = {rate:6.1%}  (per-step {PER_STEP[cfg]:.0%})")

gap = rates["set_of_marks"] - rates["pixels"]
print(f"\\nset-of-marks beats pixels by {gap:.1%} on whole-task success")
print("note: the WHOLE-TASK gap is wider than the 12-point per-step gap --")
print("compounding magnifies small per-step improvements. THIS is the number to track.")'''
))

cells.append(md(
"""**What you just saw.** A 12-point per-step edge (85% → 97%) becomes a much larger whole-task edge, because each multi-step task multiplies the per-step rate. The success-rate suite turned "set-of-marks feels better" into a defensible, version-stamped number — and it would just as readily catch a *regression* when you swap a model or change a prompt."""
))

# 5f. Pitfall: headline scores ------------------------------------------------
cells.append(md(
"""## 6 · ⚠️ Pitfall: trusting a headline WebArena / OSWorld score

It is tempting to quote a leaderboard number. Don't lean on it. Public suites differ in tasks, environments, and harness, and capability moves fast — a headline "X% on WebArena" tells you little about *your* tasks. The number that matters is **your** suite's, on **your** tasks, **version-stamped** "as of …".

Our fixture carries an `as_of` stamp for exactly this reason. Treat any external score as provisional; treat your own frozen suite as the source of truth (Ch 22)."""
))

cells.append(code(
'''# The suite is version-stamped on purpose. A result without an "as_of" and a fixed
# task set is a rumor, not a measurement.
print(f"our measurement is stamped: suite={suite['name']!r}, as_of={suite['as_of']!r}")
print(f"task ids (frozen): {[t['id'] for t in suite['tasks']]}")
print("\\nRule of thumb: report 'set-of-marks: {:.0%} on <suite> as of {}',".format(
    rates['set_of_marks'], suite['as_of']))
print("never just 'our agent is good at web tasks'. A score without a frozen suite")
print("and a date is unfalsifiable -- and a headline leaderboard number is not YOUR number.")'''
))

# 6. Senior lens --------------------------------------------------------------
cells.append(md(
"""## 🎯 Senior lens: grounding + the success harness is where you out-engineer the model

Providers ship the perception-and-action loop. You supply the **set-of-marks layer**, the **per-step verification**, and the **success-rate harness** that tells you whether a model swap helped or quietly regressed. That is durable infrastructure — it keeps paying off as the underlying models improve, because **a better model on a structured, measured loop beats a better model clicking pixels in the dark.**

Two judgments make it real. First, **climb the grounding ladder before you tune prompts**: a real API or a DOM action removes whole classes of failure that no amount of prompt-wrangling fixes, and set-of-marks is cheap to add for a large reliability win. Second, **make the suite the contract**: fixed tasks, programmatic end-state checks, a date stamp, success rate tracked over time. When someone proposes "let's upgrade the model," your answer isn't an opinion — it's a re-run of the frozen suite and a diff in the number."""
))

# 7. Recap --------------------------------------------------------------------
cells.append(md(
"""## Recap

- **Climb the grounding ladder:** real API → DOM/accessibility actions → set-of-marks → raw pixels. Every rung up buys per-step reliability, which compounds.
- **Set-of-marks** overlays numbered ids on interactive elements so the model acts by *id*, not coordinate — robust to layout shifts that break pixel clicks.
- **Verify each action** against the world's end-state (URL / element / value) and **replan** on mismatch instead of compounding a misclick.
- A **frozen task-success harness** with **programmatic end-state checks** is how you measure — not the agent's narrated success. Same discipline as Ch 22's golden suites.
- The whole-task gap between configs is **wider** than the per-step gap, because compounding magnifies small improvements — track the whole-task number.
- Treat headline WebArena / OSWorld scores as provisional; **your** version-stamped suite on **your** tasks is the source of truth."""
))

# 8. Exercises ----------------------------------------------------------------
cells.append(md(
"""## Exercises

Each exercise *changes* something and asks you to predict the result first. (Solutions arrive in `solutions/` in Phase 2.)

1. **Add a task to the suite and re-measure.** Append a 3-step task to `data/task_suite.json` (with an `expected_cart`). Predict whether the overall success rates move up or down, then re-run `measure` for both configs.
2. **Add a verify check.** Extend `act_and_verify` to also assert a specific element id is present after the action. Predict what happens when you point it at a missing id, then run.
3. **Close the gap with a third config.** Add a `dom` config to `PER_STEP` at 0.99 per step. Predict its whole-task rate relative to `set_of_marks`, then measure.
4. **Make pixels fail honestly.** Modify the simulated agent so `pixels` succeeds only when *no* layout shift occurred (add a `shift_prob` to each task). Predict how that widens the gap, then measure."""
))

cells.append(code("# Exercise 1 -- your code here\n"))
cells.append(code("# Exercise 2 -- your code here\n"))
cells.append(code("# Exercise 3 -- your code here\n"))
cells.append(code("# Exercise 4 -- your code here\n"))

# 9. Next ---------------------------------------------------------------------
cells.append(md(
"""## Next

You raised per-step reliability and learned to *prove* it. Where this goes:

- 📓 **Back to:** [`47-01-sandboxed-computer-use-loop.ipynb`](47-01-sandboxed-computer-use-loop.ipynb) — the safety harness these reliability gains run *inside*. Safety and reliability are two halves of the same harness.
- 🔧 **Mirrors blueprint:** the frozen success-suite here follows the structure of [`../../../blueprints/eval-harness/`](../../../blueprints/eval-harness/) — fixed tasks, programmatic checks, version-stamped scores.
- 🎓 **Capstone:** a computer-use tool added to `capstone/agents/tools/` should ship with its *own* frozen success-suite and run behind 47-01's human-in-the-loop gate — never autonomous for irreversible actions.
- 📖 **Book:** §47.3 (grounding on structure; #term set-of-marks; verify-and-replan; the grounding-ladder #tip; measuring task-success on a fixed suite; the 🎯 "grounding + eval is where you out-engineer a raw model call"). Cross-reference Ch 22 for the evaluation-harness discipline."""
))

# --- assemble ---------------------------------------------------------------
nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
    f.write("\n")

print("wrote", OUT, "with", len(cells), "cells")
