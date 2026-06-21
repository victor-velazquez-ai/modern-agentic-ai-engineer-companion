"""Generate the Ch 48 companion notebooks as valid nbformat-4 files.

Run from this folder:  python _build_nb.py
Outputs are cleared (execution_count null, outputs []). This helper is a build
tool, not part of the course; it can be deleted after generation.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent


def md(text):
    # Store source as a list of lines, each ending in \n except the last,
    # mirroring how Jupyter writes cells.
    lines = text.split("\n")
    src = [l + "\n" for l in lines[:-1]] + [lines[-1]]
    if src == [""]:
        src = []
    return {"cell_type": "markdown", "metadata": {}, "source": src}


def code(text):
    lines = text.split("\n")
    src = [l + "\n" for l in lines[:-1]] + [lines[-1]]
    if src == [""]:
        src = []
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": src,
    }


def write_nb(name, cells):
    nb = {
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
    out = HERE / name
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


# ===================================================================
# 48-01 — customization-triage.ipynb  (concept-lab, worksheet-flavored)
# ===================================================================
cells_01 = []

cells_01.append(md(
"""# Customization triage: prompt vs RAG vs fine-tune, decided on evidence

> \U0001F4D3 *Companion to* **Modern Agentic AI Engineer** *· Ch 48 §48.1 · type: concept-lab*

*One-line promise:* turn the chapter's three-lever triage into a small **decision tool**, run real scenarios through it, and defend a prompt-vs-RAG-vs-fine-tune call with a *measured* signal instead of fashion."""
))

cells_01.append(md(
"""## \U0001F9E0 Why this matters

\"Should we fine-tune?\" is the most expensive question a team answers on vibes. The three levers change *different things*: **prompting changes instructions**, **RAG changes available knowledge**, **fine-tuning changes the weights — the model's default behavior**. Reach for them top to bottom — prompt first, retrieve second, train only when the first two *demonstrably plateau on a measured eval*. The senior skill isn't knowing the levers; it's matching each task to the cheapest one that moves the metric, and knowing that the eval is the prerequisite, not the afterthought."""
))

cells_01.append(md(
"""## Objectives & prereqs

**By the end you can:**
- Map a task to the right lever (prompt / RAG / fine-tune) and say *what each one changes*.
- Run a set of real scenarios through a reusable decision function and check yourself against gold answers.
- Explain why fine-tuning to *inject knowledge* is the classic failure — and where facts vs form actually belong.
- Use a measured *plateau* as the trigger for training: \"an agent you cannot evaluate is an agent you cannot train.\"

**Prereqs:** Ch 10 (prompting) · Ch 13 (RAG) · Ch 22 (evals — the measured plateau). Run the setup cell first.

**Cost:** none. Fully offline — a decision function plus a mocked metric. No API key, no network."""
))

cells_01.append(md("## Setup"))

cells_01.append(code(
'''import json
import os
import random
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads a git-ignored .env if present; never hardcode keys

# This notebook is 100% offline: a decision function and a mocked metric. The
# MOCK switch is here for consistency with the rest of the course; no live model
# is ever called from 48-01.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(7)  # the mocked plateau demo below is reproducible

DATA = Path("data")


def load_scenarios():
    return json.loads((DATA / "scenarios.json").read_text(encoding="utf-8"))


print("MOCK =", MOCK, "| this notebook runs fully offline (no model calls)")'''
))

cells_01.append(md(
"""## The three levers — what each one *changes*

Pin the mental model before the mechanics. Same axis the chapter draws: you **tell** someone the dress code (prompt), you **hand them the manual** (RAG), or you **apprentice them until the habit is automatic** (fine-tune). Habits are powerful and cheap to execute — and slow and costly to retrain when requirements change next quarter."""
))

cells_01.append(code(
'''LEVERS = {
    "prompt": {
        "changes": "instructions",
        "reach_when": "Behavior, tone, format, or workflow needs to change. Always the "
                      "first move: fast, cheap, reversible, no infra.",
        "wont": "Hold beyond the context limit, or add a capability the model lacks.",
    },
    "rag": {
        "changes": "available knowledge",
        "reach_when": "Answers depend on private, large, or changing knowledge; you need "
                      "citations and instant updates.",
        "wont": "Change style or behavior — it adds facts, not skills.",
    },
    "fine-tune": {
        "changes": "the model's weights (its default behavior)",
        "reach_when": "A narrow, stable task needs consistent style/format, or you want a "
                      "smaller cheaper model to match a big one on that task.",
        "wont": "Reliably add new facts — knowledge belongs in retrieval, not weights.",
    },
}

for name, spec in LEVERS.items():
    print(f"{name:>10}  changes: {spec['changes']}")'''
))

cells_01.append(md(
"""## Encode the triage as a decision function

The chapter's triage table is really a tiny rule set. Encoding it makes the policy *executable and testable* — you can run a task through it and get a justified lever, not a hunch. The signals below are deliberately the ones the chapter calls out: volatile/attributable facts → RAG; narrow + stable + high-volume + format/behavior → fine-tune; everything else starts at the prompt."""
))

cells_01.append(code(
'''def triage(task: str) -> dict:
    \"\"\"Map a task description to a recommended lever + rationale.

    Mirrors §48.1's table. Order matters: we check the 'facts' trap first
    (the most common expensive mistake), then the fine-tune bar, else prompt.
    \"\"\"
    t = task.lower()

    wants_facts = any(w in t for w in [
        "cite", "citation", "current", "live", "price", "sku", "policy doc",
        "internal doc", "manual", "knowledge the model", "never seen", "inject",
    ])
    volatile = any(w in t for w in ["change", "quarterly", "live", "current", "update"])

    narrow_stable = any(w in t for w in ["narrow", "one ", "single", "stable", "schema"])
    high_volume = any(w in t for w in ["million", "volume", "cheaper", "50x", "10x", "at scale"])
    form_behavior = any(w in t for w in ["schema", "json", "format", "tone", "style", "house"])

    if wants_facts:
        return {
            "lever": "rag",
            "why": "The need is knowledge that is private/large/changing or must be cited. "
                   "Facts belong in retrieval; baking them into weights half-memorizes and "
                   "goes stale.",
        }
    if narrow_stable and (high_volume or form_behavior):
        return {
            "lever": "fine-tune",
            "why": "Narrow, stable task needing consistent form/behavior at volume. Weights "
                   "encode habit; the volume amortizes the (depreciating) training asset.",
        }
    return {
        "lever": "prompt",
        "why": "A behavior/tone/workflow change expressible as an instruction. Always try "
               "this first: reversible, cheap, no infra — and often enough.",
    }


# Smoke-test it on a couple of obvious cases.
print(triage("Adopt a warmer brand voice across all features")["lever"])
print(triage("Quote our 12,000 live SKUs and current prices")["lever"])'''
))

cells_01.append(md(
"""### \U0001F52E Predict

Before you run the next cell, predict the right lever for this task:

> *\"Answers must cite our current internal docs, which change quarterly.\"*

Jot **prompt / RAG / fine-tune** and one sentence of why. The pull toward \"just fine-tune on the docs\" is strong — resist it and reason from *what each lever changes*. Now reveal."""
))

cells_01.append(code(
'''hard = "Answers must cite our current internal docs, which change quarterly."
verdict = triage(hard)
print("lever:", verdict["lever"])
print("why:  ", verdict["why"])'''
))

cells_01.append(md(
"""The answer is **RAG**, not fine-tune. *Current* + *cite* + *change quarterly* are three independent tells that this is a knowledge problem with an attribution and freshness requirement. Weights can't be re-attributed and can't be updated without retraining; retrieval can do both in seconds."""
))

cells_01.append(md(
"""## Run the scenario set — check yourself against gold

`data/scenarios.json` holds tasks paired with the *correct* lever and a rationale. Run them all through `triage()` and score exact-match. This is your self-check that you internalized the table, not just memorized one example."""
))

cells_01.append(code(
'''scenarios = load_scenarios()
correct = 0
for s in scenarios:
    got = triage(s["task"])["lever"]
    ok = got == s["lever"]
    correct += ok
    mark = "ok " if ok else "MISS"
    print(f"{s['id']} [{mark}] predicted={got:<10} gold={s['lever']:<10} {s['task'][:54]}")

print(f"\\ntriage accuracy: {correct}/{len(scenarios)} = {correct/len(scenarios):.0%}")
print("(Any MISS is a teaching moment: read its rationale and see which signal you'd add.)")'''
))

cells_01.append(md(
"""## ⚠️ Pitfall: fine-tuning to *inject knowledge*

The single most expensive mistake in this chapter: feeding your docs in as *training data* and expecting the model to recall them. It half-memorizes, blends facts, and hallucinates fluently in your house style — worse than vanilla RAG, and unfixable without retraining. Below is a deliberately crude mock that shows the *shape* of the failure: a \"fine-tuned-on-facts\" model that confidently invents, versus a RAG path that grounds and can abstain."""
))

cells_01.append(code(
'''KB = {
    "refund-policy": "Refunds are issued within 5 business days to the original card.",
    "sla": "Enterprise SLA is 99.9% monthly uptime.",
}


def answer_finetuned_on_facts(question: str) -> str:
    \"\"\"Anti-pattern: facts 'trained in'. MOCK simulates lossy recall + fluent invention.\"\"\"
    q = question.lower()
    # It sometimes half-remembers the right shape but corrupts the detail...
    if "refund" in q:
        return "Refunds are issued within 30 days via store credit."  # WRONG, but fluent
    if "sla" in q:
        return "Our SLA guarantees 100% uptime, always."  # WRONG, confidently
    return "Yes, that is covered under our standard policy."  # invented, no source


def answer_rag(question: str) -> str:
    \"\"\"Facts in retrieval: grounded, attributable, and able to say 'I don't know'.\"\"\"
    q = question.lower()
    for key, fact in KB.items():
        if key.split("-")[0] in q:
            return f"{fact} [source: {key}]"
    return "The provided context does not cover this."  # the escape hatch


for q in ["What is the refund window?", "What is the SLA?", "Do you cover water damage?"]:
    print("Q:", q)
    print("  fine-tuned-on-facts:", answer_finetuned_on_facts(q))
    print("  RAG:                ", answer_rag(q))
    print()'''
))

cells_01.append(md(
"""Read the contrast: the \"trained-in facts\" path is **fluent and wrong** and gives you no source to check; the RAG path is **grounded, cited, and abstains** when it doesn't know. The rule the chapter hammers: **fine-tune for form and behavior; retrieve for facts.**"""
))

cells_01.append(md(
"""## The plateau that *earns* a fine-tune

You only descend to training when prompting and RAG **demonstrably plateau on a measured eval**. Here's a tiny mocked metric across the three levers on a *narrow formatting* task: prompting and RAG lift quality but stall below the bar; only training the habit clears it. The point isn't the numbers — it's that a number, not a hunch, is what licenses the spend."""
))

cells_01.append(code(
'''def measured_score(lever: str) -> float:
    \"\"\"Mocked eval score (0..1) on a narrow strict-format task. Seeded, deterministic.\"\"\"
    # A task that is purely about consistent form: prompting and RAG help a bit,
    # but format adherence is a *habit* that only weight-tuning makes reliable.
    base = {"prompt": 0.71, "rag": 0.73, "fine-tune": 0.94}[lever]
    jitter = (random.random() - 0.5) * 0.02  # tiny seeded noise
    return round(min(1.0, base + jitter), 3)


BAR = 0.90  # the quality gate this task must clear to ship
print(f"target on the eval: {BAR:.0%} format-adherence\\n")
for lever in ["prompt", "rag", "fine-tune"]:
    s = measured_score(lever)
    status = "clears bar" if s >= BAR else "PLATEAU below bar"
    print(f"  {lever:<10} score={s:.0%}  -> {status}")

print("\\nPrompt and RAG plateau; the measured gap is the evidence that licenses training.")
print("No eval = no plateau = no justification. The eval is the prerequisite.")'''
))

cells_01.append(md(
"""## \U0001F4CB Your decision checklist

Fill this in for a real task of your own (edit the strings). It's the chapter's closing checklist, made runnable — a yes-row that's actually \"no\" is a reason to *not* fine-tune yet."""
))

cells_01.append(code(
'''my_task = "TODO: describe your task in one line"

checklist = {
    "prompt_and_rag_plateaued_on_a_measured_eval": False,  # set True only with numbers
    "task_is_narrow_and_stable_enough_to_amortize": False,
    "have_or_can_collect_thousands_of_curated_examples": False,
    "held_out_test_set_defined_BEFORE_training": False,
    "dataset_clean_of_pii_and_licensing_and_versioned": False,
    "serving_and_rollback_plan_exists": False,  # Ch 39: adapters on a shared base
    "owner_named_to_re_run_the_call_on_next_base_model": False,
}

print("task:", my_task)
ready = all(checklist.values())
for k, v in checklist.items():
    print(f"  [{'x' if v else ' '}] {k}")
print(f"\\nVerdict: {'consider fine-tuning' if ready else 'NOT YET — stay on prompt/RAG'}")'''
))

cells_01.append(md(
"""## \U0001F3AF Senior lens

Customization is a **portfolio decision under depreciation**. Every fine-tune is an asset that decays — the next base-model release may match your tuned model out of the box, and your adapter doesn't transfer. So capture the *durable* assets — **the curated dataset and the eval** — because those outlive any checkpoint; customize only where volume is high and the task is stable enough to amortize the work; and keep the prompt-based fallback alive so a model swap is an afternoon, not a quarter. Teams that treat data and evals as the product, and weights as a disposable artifact, win this game."""
))

cells_01.append(md(
"""## Recap

- Three levers, three different effects: **prompt = instructions**, **RAG = knowledge**, **fine-tune = default behavior (weights)**. Reach top to bottom.
- A triage *function* makes the policy executable and self-checkable against gold scenarios.
- **Never fine-tune to inject knowledge** — it's fluent, wrong, and unattributable. Facts → retrieval; form/behavior → weights.
- Training is licensed by a **measured plateau**, not fashion. No eval, no plateau, no justification.
- The durable assets are the **dataset and the eval**; weights depreciate. Keep the prompt fallback alive."""
))

cells_01.append(md(
"""## Exercises

1. **Break the triage.** Write a task you think `triage()` will misclassify, predict the (wrong) lever, then run it. Which *signal* would you add to `triage()` to fix it without breaking the scenarios that pass?
2. **Add a scenario.** Append one row to `data/scenarios.json` with your own gold lever + rationale. Re-run the scoring cell and confirm the accuracy line updates.
3. **Move the bar.** In the plateau cell, change `BAR` to `0.95` and to `0.70`. At which bar does fine-tuning stop being justified, and what does that tell you about choosing the gate *before* you measure?
4. **Fill the checklist for real.** Replace `my_task` and set the booleans honestly for a task at your job. If the verdict is \"NOT YET,\" name the one row that would flip it first."""
))

cells_01.append(code("# Exercise 1 — a task you think triage() gets wrong; predict, then run.\n"))
cells_01.append(code("# Exercise 2 — add a scenario to data/scenarios.json and re-score.\n"))
cells_01.append(code("# Exercise 3 — sweep BAR in {0.70, 0.95} and read the verdict.\n"))

cells_01.append(md(
"""## Next

- **Next notebook:** [`48-02-lora-peft-small-model.ipynb`](./48-02-lora-peft-small-model.ipynb) — ⚠️ optional/heavy. *If* the triage above says \"fine-tune,\" see what LoRA actually changes (and what it doesn't), with a fully-mocked default so it still runs free.
- **The eval that gates every technique:** [`blueprints/eval-harness/`](../../../blueprints/eval-harness/) — the chapter's #keyidea is that your eval suite *is* the reward function and the rejection-sampling verifier.
- **Serving any custom model:** the `capstone/` serving + rollback plane (Ch 39) — a fine-tuned model is \"an adapter or a deployment\" with the same rollback discipline."""
))

write_nb("48-01-customization-triage.ipynb", cells_01)
print("wrote 48-01")


# ===================================================================
# 48-02 — lora-peft-small-model.ipynb  (walkthrough, optional/heavy)
# ===================================================================
cells_02 = []

cells_02.append(md(
"""# ⚠️ Optional/heavy: a LoRA fine-tune you can read

> \U0001F4D3 *Companion to* **Modern Agentic AI Engineer** *· Ch 48 §48.2–§48.5 · type: walkthrough*

*One-line promise:* read and run a *minimal* LoRA adapter fit on a tiny model — see trainable params drop under 1% — and place DPO, distillation, and the agent-training ladder on the conceptual cost ladder. **The default run is fully mocked: no GPU, no key, no network.**"""
))

cells_02.append(md(
"""## \U0001F9E0 Why this matters

LoRA is a *commodity*: freeze the base model, learn small low-rank adapter matrices, train well under 1% of the parameters, ship the adapter as a tiny swappable file. Knowing the API is not the skill. The skill is knowing that **data curation and a pre-defined eval are the real work**, that an adapter changes *form, not facts*, and that everything above LoRA — DPO, distillation, agentic RL — is a **cost ladder** you descend only when the cheaper rung plateaus. You'll mostly *commission or evaluate* these, so you need to know what each buys and what it costs."""
))

cells_02.append(md(
"""## Objectives & prereqs

**By the end you can:**
- Explain what LoRA freezes and what it trains, and why `print_trainable_parameters()` shows <1%.
- Run a *toy* adapter fit (mocked by default) with a **held-out set defined before training**.
- Predict and confirm that an adapter enforces a **format** but cannot **recall a new fact**.
- Locate **DPO**, **distillation**, and the **agent-training ladder** (tool-use FT → PRM → agentic RL → synthetic trajectories) on the cost ladder.

**Prereqs:** `48-01` (triage) · Ch 22 (define the eval/held-out set *before* training) · Ch 39 (serving adapters on a shared base, rollback) — referenced, not required to run.

**Cost:** `MOCK=1` (default) is free, offline, GPU-free. `MOCK=0` actually trains and needs a GPU + extra deps — declared in the gate cell below and **skipped in CI**."""
))

cells_02.append(md(
"""## ⚠️ Gate: this notebook is optional and heavy

The default path loads a **canned training log + adapter stats** so the notebook runs green for everyone. The live path (`MOCK=0`) trains a real toy adapter and needs:

- a GPU (even a tiny base is slow on CPU),
- extra packages **not** in the base `requirements.txt`: `peft`, `transformers`, `datasets`, `accelerate`, `torch`,
- a small local base model download (e.g. `Qwen/Qwen2.5-0.5B`).

Leave `COMPANION_MOCK=1` unless you specifically want to train. The mock is faithful to the *shapes* you'd see live."""
))

cells_02.append(code(
'''import json
import os
import random
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # git-ignored .env if present; never hardcode keys

# MOCK=1 (default): load canned train log + adapter stats. Runs FREE, OFFLINE,
# NO GPU, NO KEY. MOCK=0: actually train (needs GPU + the extra deps above).
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

# Tiny local base used ONLY on the live path. Small on purpose so a curious
# reader with a GPU can finish in minutes; never downloaded in MOCK mode.
BASE_MODEL = os.getenv("COMPANION_BASE_MODEL", "Qwen/Qwen2.5-0.5B")

random.seed(7)  # any mock jitter is reproducible

DATA = Path("data")

print("MOCK =", MOCK, "| base (live only) =", BASE_MODEL)
if not MOCK:
    print("\\n⚠️  MOCK=0: this will train a real adapter and needs a GPU + peft/transformers/datasets/accelerate/torch.")'''
))

cells_02.append(md(
"""## Step 1 — curate the data, and hold out a test set *first*

The unglamorous truth: the technique is a commodity; **data curation wins fine-tunes**. A few thousand clean, deduplicated, correctly-formatted examples that actually exhibit the target behavior beat a million scraped ones. Our toy task is pure *form*: turn a free-text order note into a strict JSON status. We split a held-out set **before** training — the eval is defined first, or you can't tell if training helped."""
))

cells_02.append(code(
'''def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


train = read_jsonl(DATA / "toy_train.jsonl")
holdout = read_jsonl(DATA / "toy_holdout.jsonl")

print(f"{len(train)} train examples, {len(holdout)} holdout (defined BEFORE training)")
print("\\nexample train pair:")
print("  in :", train[0]["input"])
print("  out:", train[0]["output"])
print("\\nholdout deliberately mixes two probes:")
for h in holdout:
    print(f"  {h['id']} tests={h['tests']:<7} {h['input'][:50]}")'''
))

cells_02.append(md(
"""## Step 2 — configure LoRA (freeze base, train tiny adapters)

This is the code shape from §48.2: pick a low rank `r`, a handful of `target_modules` on the attention projections, and wrap the frozen base with `get_peft_model`. `print_trainable_parameters()` reveals the whole point — you're training a sliver. In `MOCK=1` we load the captured numbers from `data/adapter_stats.json` instead of building a real model."""
))

cells_02.append(code(
'''LORA_CONFIG = {
    "r": 8,                       # the rank — the main capacity/size dial
    "lora_alpha": 16,             # scaling; commonly ~2x r
    "lora_dropout": 0.05,
    "target_modules": ["q_proj", "v_proj"],  # which projections get adapters
    "task_type": "CAUSAL_LM",
}


def configure_lora():
    \"\"\"Return (trainable, total, percent). MOCK: read captured stats; live: build it.\"\"\"
    if MOCK:
        stats = json.loads((DATA / "adapter_stats.json").read_text(encoding="utf-8"))
        return stats["trainable_params"], stats["base_total_params"], stats["trainable_percent"]
    # --- live path (MOCK=0): the real §48.2 shape ---
    from peft import LoraConfig, get_peft_model       # noqa: F401  (extra dep)
    from transformers import AutoModelForCausalLM      # noqa: F401  (extra dep)

    base = AutoModelForCausalLM.from_pretrained(BASE_MODEL)
    config = LoraConfig(**LORA_CONFIG)
    model = get_peft_model(base, config)
    model.print_trainable_parameters()
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    return trainable, total, trainable / total


trainable, total, pct = configure_lora()
print(f"trainable params: {trainable:,}")
print(f"total params:     {total:,}")
print(f"trainable %:      {pct:.4%}   <-- the entire point of PEFT")'''
))

cells_02.append(md(
"""Under **1%** of the parameters are trained. The frozen base is shared; the adapter is a small file you can swap per tenant or task and roll back instantly (Ch 39). QLoRA pushes further — quantize the frozen base to 4-bit and a 7–13B fine-tune fits on one GPU."""
))

cells_02.append(md(
"""## Step 3 — \"train\" and read the loss curve

On the live path you'd run a `Trainer` for a few epochs. In `MOCK=1` we load `data/train_log.json` — a captured loss curve — so you can read the *shape* (loss falling, then flattening) without a GPU. A falling-then-flat curve on a tiny set is exactly what format-shaping looks like: the model is learning the *habit*, fast."""
))

cells_02.append(code(
'''def get_train_log():
    if MOCK:
        return json.loads((DATA / "train_log.json").read_text(encoding="utf-8"))
    # --- live path would assemble + run a Trainer and return its history ---
    raise NotImplementedError(
        "Live training loop is left as the opt-in heavy path; wire up "
        "transformers.Trainer over the train split and capture .state.log_history."
    )


log = get_train_log()
print(f"run: {log['run_id']}  base: {log['base_model']}  method: {log['method']}")
print(f"epochs: {log['config']['epochs']}  r: {log['config']['r']}  "
      f"targets: {log['config']['target_modules']}\\n")
print("loss curve:")
for s in log["steps"]:
    bar = "█" * round(s["loss"] * 8)
    print(f"  epoch {s['epoch']:.2f}  loss {s['loss']:.2f}  {bar}")
print(f"\\nwall clock: {log['wall_clock_seconds']}s on {log['device']}")'''
))

cells_02.append(md(
"""## \U0001F52E Predict

Two probes wait in the holdout set. Before you run the eval, predict each:

1. The **format probe** (`tests=format`): a new order note — will the adapter emit the strict JSON shape it was trained on?
2. The **fact probe** (`tests=fact`): \"what is the capital of the country where this order was delivered?\" — a fact never in the training data.

Write **yes/no** for each. The chapter's whole point about *form vs facts* is riding on your answer. Now evaluate."""
))

cells_02.append(code(
'''def adapter_infer(example: dict) -> str:
    \"\"\"What the LoRA-tuned model returns. MOCK: a faithful stand-in of the behavior.

    The adapter reliably reproduces the *trained format* but cannot conjure a
    *new fact* it never saw — the core form-vs-facts lesson, made observable.
    \"\"\"
    if not MOCK:
        # live: tokenize prompt, model.generate(...), decode. (heavy path)
        raise NotImplementedError("Run generation on the merged/adapter model here.")
    text = example["input"].lower()
    # FORMAT habit: the adapter learned to map notes -> strict JSON status.
    import re
    m = re.search(r"order (\\d+)", text)
    oid = int(m.group(1)) if m else None
    if "deliver" in text:
        status, eta = "delivered", None
    elif "pack" in text or "queue" in text or "process" in text:
        status, eta = "processing", None
    elif "ship" in text or "out for delivery" in text or "depot" in text:
        status = "shipped"
        d = re.search(r"(\\d{4}-\\d{2}-\\d{2})", example["input"])
        eta = d.group(1) if d else None
    else:
        status, eta = "unknown", None
    # The FACT probe asks for world knowledge never in the data: the tuned model
    # does NOT gain it. A format-tuned model will dutifully emit its trained shape
    # and simply has no field for the fact — it cannot recall what it never learned.
    if "capital" in text:
        return json.dumps({"order_id": oid, "status": status, "eta": eta})  # no 'capital' — fact absent
    return json.dumps({"order_id": oid, "status": status, "eta": eta})


def eval_holdout():
    fmt_ok = fmt_total = fact_handled = fact_total = 0
    for h in holdout:
        out = adapter_infer(h)
        if h["tests"] == "format":
            fmt_total += 1
            try:
                obj = json.loads(out)
                ok = set(obj.keys()) == {"order_id", "status", "eta"}
            except json.JSONDecodeError:
                ok = False
            fmt_ok += ok
            print(f"  {h['id']} format  {'PASS' if ok else 'FAIL'}  -> {out}")
        else:
            fact_total += 1
            # The 'right' behavior is to NOT invent the fact. Our adapter emits the
            # trained shape with no fabricated capital -> it did not gain the fact.
            invented_fact = "capital" in out.lower()
            fact_handled += (not invented_fact)
            print(f"  {h['id']} fact    {'did NOT invent (good)' if not invented_fact else 'HALLUCINATED'}  -> {out}")
    print(f"\\nformat adherence: {fmt_ok}/{fmt_total}")
    print(f"fact probes that correctly gained-no-new-fact: {fact_handled}/{fact_total}")


eval_holdout()'''
))

cells_02.append(md(
"""Confirmed: the adapter **enforces the format** (every format probe passes) and **does not recall a new fact** (it never invents a capital it was never taught). This is §48.2 made observable — *fine-tune for form and behavior; retrieve for facts.* If you needed that capital, the fix is RAG, not more epochs."""
))

cells_02.append(md(
"""## ⚠️ Pitfall: a dirty, duplicated, under-curated dataset

The fastest way to waste a fine-tune is bad data. A few thousand *clean* examples beat a million scraped ones — and duplicates, label noise, leaked PII, and licensing problems all quietly poison the result. Here's a tiny curation pass that catches the usual suspects before they reach the trainer."""
))

cells_02.append(code(
'''def audit_dataset(rows):
    seen, dups, empties, pii = set(), [], [], []
    import re
    email = re.compile(r"[\\w.+-]+@[\\w-]+\\.[\\w.-]+")
    for r in rows:
        key = (r["input"].strip().lower(), r["output"].strip())
        if key in seen:
            dups.append(r["id"])
        seen.add(key)
        if not r["input"].strip() or not r["output"].strip():
            empties.append(r["id"])
        if email.search(r["input"]) or email.search(r["output"]):
            pii.append(r["id"])
    return {"duplicates": dups, "empties": empties, "possible_pii": pii}


# Inject a couple of bad rows to show the audit firing (NOT added to training).
dirty = train + [
    {"id": "bad-dup", "instruction": train[0]["instruction"], "input": train[0]["input"], "output": train[0]["output"]},
    {"id": "bad-pii", "instruction": "x", "input": "Order 1 for jane@acme.com shipped", "output": "{}"},
]
report = audit_dataset(dirty)
for k, v in report.items():
    print(f"{k:>14}: {v}")
print("\\nVersion the *clean* set, and define the eval before you collect a single example.")'''
))

cells_02.append(md(
"""## \U0001F9E0 The cost ladder beyond LoRA (conceptual — nothing trains here)

LoRA tunes single-turn *behavior*. Agents add **multi-step trajectories** — sequences of tool calls and decisions — and a rougher toolkit grew up around improving that whole loop. You'll mostly *buy, commission, or decline* these, so the job is knowing what each rung buys and what it costs. Read this as a **cost ladder**: descend only when the cheaper rung demonstrably plateaus on your eval."""
))

cells_02.append(code(
'''COST_LADDER = [
    {
        "technique": "Tool-use fine-tuning",
        "buys": "Reliable, correctly-formatted tool calls from a smaller, cheaper model",
        "when_cost": "Stable tool set, proven task; cheap — the standard cost-down move",
    },
    {
        "technique": "Process reward model (PRM)",
        "buys": "Step-level credit so long-horizon training actually converges",
        "when_cost": "Long multi-step tasks; needs per-step labels or a learned grader",
    },
    {
        "technique": "Agentic RL on rollouts",
        "buys": "Genuine multi-step competence beyond single-turn tuning",
        "when_cost": "Highest cost: rollout environment, infra, and a reward you trust",
    },
    {
        "technique": "Synthetic trajectories",
        "buys": "Distill a strong agent's verified successes into a small one",
        "when_cost": "A good verifier exists; just filtered fine-tuning — much cheaper than full RL",
    },
]

print("LEVERS FOR IMPROVING AGENTS (read top->bottom as a cost ladder)\\n")
for rung in COST_LADDER:
    print(f"• {rung['technique']}")
    print(f"    buys : {rung['buys']}")
    print(f"    cost : {rung['when_cost']}\\n")'''
))

cells_02.append(md(
"""### DPO and distillation, in one breath each

- **DPO (direct preference optimization)** reaches an RLHF-like result *without* the RL machinery: train directly on **(prompt, preferred, rejected)** triples with a simple loss. It fits cases where quality is easy to *judge* but hard to *specify* (tone, helpfulness, fuzzy policy), and comparisons are far cheaper to collect than gold outputs.
- **Distillation** uses a strong *teacher* to teach a small *student*: generate or grade data with the teacher, fine-tune the student on it. It's the economic engine — prototype on a frontier model, then distill the proven behavior into something **10–50× cheaper** to serve at volume."""
))

cells_02.append(code(
'''# A DPO training row is just a triple. No RL, no reward model — a pair the model
# learns to prefer. (Shape only; we are not training.)
dpo_example = {
    "prompt": "Customer: my package is late and I'm furious.",
    "preferred": "I'm sorry it's late — here's exactly where it is and what I'll do now: ...",
    "rejected": "Per policy section 4.2, delays are not guaranteed against.",
}
print("a DPO triple (what you'd collect, by the thousand):")
print(json.dumps(dpo_example, indent=2))
print("\\nNote: pairwise 'A is better than B' is far cheaper to label than a perfect gold answer.")'''
))

cells_02.append(md(
"""### \U0001F511 The signal under all of it (the chapter's key idea)

Every rung depends on one thing: **a signal that says the trajectory was good.** That signal *is* your eval suite from Ch 22 — mechanically, the same harness is the reward function and the rejection-sampling verifier. **An agent you cannot evaluate is an agent you cannot train.** And whatever you train still has to be *served*: a tuned agent model is an adapter or a deployment on the same serving plane (Ch 39), with the same rollback discipline."""
))

cells_02.append(md(
"""## \U0001F3AF Senior lens

Every fine-tune is an asset that **depreciates** — the next base model may match it out of the box, and your adapter doesn't transfer. So keep the prompt fallback alive so a base-model swap is an *afternoon, not a quarter*; treat the **curated dataset and the eval** as the durable product and the weights as a disposable artifact; and descend the cost ladder one rung at a time, only when a measured plateau forces you. The team that owns the data and the eval owns the capability — whoever owns this quarter's checkpoint owns a liability with a half-life."""
))

cells_02.append(md(
"""## Recap

- **LoRA = freeze the base, train low-rank adapters (<1% of params)**; the adapter is a tiny swappable, roll-back-able file. QLoRA quantizes the frozen base to fit bigger models on one GPU.
- **Data curation + a pre-defined held-out eval are the real work**; the technique is a commodity. Define the eval *before* collecting data.
- An adapter changes **form, not facts** — it enforces a format but cannot recall new knowledge (that's RAG's job).
- **DPO** trains on preference triples without RL; **distillation** compresses a teacher into a 10–50× cheaper student.
- The **agent cost ladder** (tool-use FT → PRM → agentic RL → synthetic trajectories) all rests on a trusted eval signal. No eval, no training."""
))

cells_02.append(md(
"""## Exercises

1. **Change the rank.** In `LORA_CONFIG` set `r` to 4 and to 32. 🔮 Predict how trainable-% moves *before* editing `data/adapter_stats.json` to match, then update it and re-run — does the file's `trainable_percent` agree with your intuition about rank vs adapter size?
2. **Draft a DPO triple.** Write one `(prompt, preferred, rejected)` triple for *your* product's tone. What makes the preferred answer better in a way you could *judge* but struggle to *specify*?
3. **Add a holdout probe.** Append one `tests=fact` row to `data/toy_holdout.jsonl` and confirm the eval still reports the adapter did not invent the fact. Why is \"refused to invent\" the success condition here?
4. **Place a real task on the ladder.** Pick something at your job and name which rung (tool-use FT / PRM / agentic RL / synthetic trajectories) you'd reach for — and the cheaper rung you'd prove plateaued first."""
))

cells_02.append(code("# Exercise 1 — set r in {4, 32}; predict trainable-%, then reconcile with adapter_stats.json.\n"))
cells_02.append(code("# Exercise 2 — draft a (prompt, preferred, rejected) DPO triple for your tone.\n"))
cells_02.append(code("# Exercise 3 — add a fact probe to data/toy_holdout.jsonl and re-run eval_holdout().\n"))

cells_02.append(md(
"""## Next

- **Back to the decision:** [`48-01-customization-triage.ipynb`](./48-01-customization-triage.ipynb) — the triage that should gate ever reaching this notebook.
- **The eval that gates every technique here:** [`blueprints/eval-harness/`](../../../blueprints/eval-harness/) — your eval suite *is* the reward function and the rejection-sampling verifier.
- **Serving + rollback for any custom model/adapter:** the `capstone/` serving plane (Ch 39) — a fine-tuned model is \"an adapter or a deployment\" with the same rollback discipline as any release.
- **Next chapter:** [`../49-frontier-and-staying-current/`](../49-frontier-and-staying-current/) — keeping all of this current as base models ship."""
))

write_nb("48-02-lora-peft-small-model.ipynb", cells_02)
print("wrote 48-02")
