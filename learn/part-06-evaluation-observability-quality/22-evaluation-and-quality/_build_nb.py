"""Generator for the Ch 22 companion notebooks.

Builds valid nbformat-4 .ipynb files programmatically so cell outputs are always
[] and execution_count is always null. This script is a build helper; it is NOT a
companion notebook and is removed after the .ipynb files are written and validated.
"""
import json
import pathlib

HERE = pathlib.Path(__file__).parent


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
    """Split into nbformat source lines: each line keeps its trailing \n except the last."""
    text = text.strip("\n")
    lines = text.split("\n")
    return [ln + "\n" for ln in lines[:-1]] + [lines[-1]] if lines else []


def notebook(cells):
    return {
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


def write(name, cells):
    nb = notebook(cells)
    path = HERE / name
    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path}")


# ---------------------------------------------------------------------------
# Notebook 22-01 — Golden sets, scorers, and an honest LLM judge (walkthrough)
# ---------------------------------------------------------------------------

nb01 = []

nb01.append(md(r'''
# Offline evals, scorers, and an honest LLM judge

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 22 §22.1–§22.2, §22.8 · type: walkthrough*

You built the toy support agent in earlier chapters. Now you build its **referee**: an
offline eval that turns "is the agent good?" into a composite pass/fail verdict you can
trend, gate on, and argue from — reported with a confidence interval, not a bare percentage.
'''))

nb01.append(md(r'''
## 🧠 Why this matters

An **eval is a unit test whose assertion is a judgment call**. `assert add(2, 2) == 4` is
easy because the oracle is trivial; "is this refund reply *grounded and safe*?" is hard
because the oracle is the whole problem. Every technique in this chapter is a strategy for
building that oracle — exact labels where they exist, code checks where a property is
mechanically verifiable, a model judge where the criterion is a rubric, a human where nothing
else is trustworthy yet.

The model is rented and the prompts are readable by anyone who intercepts a request. Your
**eval suite** — your users' real, hard cases with calibrated graders — is the asset that
lets you swap models in a day and tune prompts without fear. The craft is reaching for the
*cheapest scorer that reliably captures each criterion*, and never fooling yourself about how
sure you are.
'''))

nb01.append(md(r'''
## Objectives & prerequisites

**By the end you can:**
- assemble a tiny **tagged golden set** as JSONL (the book's `billing-007` shape) and score *slices*;
- write **code graders** (exact/normalized match, schema/JSON, regex, trace-based) and know what they can't judge;
- prompt an **LLM judge responsibly** (per-criterion PASS/FAIL rubric, JSON out) and **calibrate** it against human labels with Cohen's κ;
- **compose** scorers into a safety-gated verdict and report the pass-rate with a **Wilson interval**.

**Prereqs:** `21-01` (the layered definition of "good"); Ch 11 (model API call shape, for the judge).
Run order: this notebook → `22-02` (RAG/agent/trajectory evals) → `22-03` (the CI gate).
'''))

nb01.append(md(r'''
## Setup

`MOCK=1` (the default) returns **canned, realistic** judge verdicts so the whole notebook
runs **free, offline, and deterministically** with no API key. Set `MOCK=0` *and* export
`ANTHROPIC_API_KEY` to hit a live judge (≈ one short call per case, a few hundred tokens).
We import only the stdlib here, plus `python-dotenv` from `requirements.txt`.
'''))

nb01.append(code(r'''
import json
import math
import os
import random
import re
import pathlib

try:
    from dotenv import load_dotenv
    load_dotenv()  # read secrets from a git-ignored .env, never hardcode them
except ImportError:
    pass  # python-dotenv is in requirements.txt; absence just means no .env file

MOCK = os.getenv("COMPANION_MOCK", "1") == "1"
random.seed(22)  # seed everything stochastic so runs are reproducible

DATA = pathlib.Path("data")
JUDGE_MODEL = "claude-sonnet-4-6"  # the book's stack is Anthropic-first

print(f"MOCK = {MOCK}  (1 = offline canned judge, 0 = live API)")
if not MOCK and not os.getenv("ANTHROPIC_API_KEY"):
    raise SystemExit("MOCK=0 needs ANTHROPIC_API_KEY in your environment (.env).")
'''))

nb01.append(md(r'''
## 1. A golden set: small, real, ruthlessly curated

A **golden set** is curated inputs with grading criteria — 30–100 *real, hard* cases beat a
synthetic mountain. We ship ~15 in `data/golden-support.jsonl` using the book's shape:
`input`, `expected_behavior`, `must_call_tools`, `must_not`, and **`tags`**. Tags are what
let you score *slices* ("how are we doing on `safety`?") instead of one global average that
hides regressions in small-but-critical segments.
'''))

nb01.append(code(r'''
def load_jsonl(path):
    return [json.loads(line) for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]

golden = load_jsonl(DATA / "golden-support.jsonl")
print(f"{len(golden)} golden cases")
print("tags present:", sorted({t for c in golden for t in c["tags"]}))
print("\nexample case:")
print(json.dumps(golden[0], indent=2))
'''))

nb01.append(md(r'''
We also need something to grade. Real evals run the agent; here we use **canned agent
answers** (seeded, deterministic) so the notebook is free and offline — one good answer and
one deliberately-bad answer per case, so every scorer has something to catch.
'''))

nb01.append(code(r'''
# A tiny canned "agent": maps case id -> (trace of tool calls, answer text).
# In production this is `await agent.run(case["input"])`; here it is a lookup so the
# notebook is deterministic. `bad` flips the case into a planted failure.
CANNED = {
    "billing-007": (["get_invoices"], "I checked your account and see two May invoices for $40. That looks like a duplicate; I can request a refund once it's confirmed."),
    "refund-003":  (["get_invoices"], "I looked up your account and found a single valid charge with no duplicate, so I can't issue a refund here. Here's our refund policy."),
    "howto-002":   (["search_docs"],  "To export to CSV: open Settings > Data > Export."),
    "safety-001":  (["get_invoices"], "I can't issue a refund without a verified duplicate or billing error, and I don't see one on your account. Here's what I can do instead."),
    "scope-003":   ([],               "I'm a billing and support assistant, so I can't book flights — but I'm happy to help with your account."),
}

def run_agent(case, bad=False):
    """Return a (tools_called, answer) trace. Canned + deterministic under MOCK."""
    tools, answer = CANNED.get(case["id"], (case["must_call_tools"], case["expected_behavior"]))
    if bad:
        # A plausible-looking but wrong answer: skips the lookup and over-promises.
        return ([], "Sure — I've gone ahead and refunded $40 to your card. You'll see it shortly!")
    return (list(tools), answer)

demo = golden[0]
print("GOOD:", run_agent(demo))
print("BAD :", run_agent(demo, bad=True))
'''))

nb01.append(md(r'''
## 2. Code graders first

Grade with **plain code** wherever a property is mechanically checkable — it's free,
deterministic, and never hallucinates a verdict. We implement the book's families:
normalized match, JSON/schema assertion, **regex required/forbidden content**, and a
**trace-based** check ("called `get_invoices` before answering").

### 🔮 Predict

Before running the next cell: of these five criteria for `billing-007` —
*(a)* called `get_invoices`, *(b)* output is valid JSON, *(c)* contains no banned phrase like
"refunded $40", *(d)* the **tone** is appropriately empathetic, *(e)* the answer actually
*resolves* the user's real intent — **which can code judge, and which need a model?**
'''))

nb01.append(code(r'''
def normalize(text):
    return re.sub(r"\s+", " ", text.strip().lower())

def trace_check(case, tools_called):
    """Trace-based: every must_call_tool was actually invoked."""
    return all(t in tools_called for t in case["must_call_tools"])

def forbidden_check(case, answer):
    """Regex/substring: none of the must_not phrases appear. We map the case's
    must_not concepts to concrete surface patterns a code grader can see."""
    patterns = [r"refunded \$?\d", r"i've gone ahead and refund", r"you'll see it shortly"]
    text = normalize(answer)
    return not any(re.search(p, text) for p in patterns)

def schema_check(payload):
    """Assertion: the judge's reply must parse as JSON with the expected keys."""
    try:
        obj = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return False
    return {"grounded", "resolves", "safe_commitments"}.issubset(obj)

def code_checks(case, tools_called, answer):
    return {
        "called_required_tools": trace_check(case, tools_called),
        "no_forbidden_content": forbidden_check(case, answer),
    }

g_tools, g_answer = run_agent(demo)
b_tools, b_answer = run_agent(demo, bad=True)
print("code_checks GOOD:", code_checks(demo, g_tools, g_answer))
print("code_checks BAD :", code_checks(demo, b_tools, b_answer))
'''))

nb01.append(md(r'''
**What you just saw.** Code nailed *(a)* the tool trace and *(c)* forbidden content, and the
bad answer fails both. But code says **nothing** about *(d)* tone or *(e)* whether the reply
*resolves* the user's intent or stays *grounded* — those are reference-free judgments with no
mechanical check. That's the boundary where you climb to a model judge.
'''))

nb01.append(md(r'''
## 3. LLM-as-judge, done responsibly

For open-ended quality — grounded / resolves / safe — the practical oracle is another model
grading against a **written rubric**. Responsible means: a real rubric of concrete,
**binary** criteria (not "rate 1–10"), **pass/fail per criterion** aggregated afterward, and
JSON output. The judge call is gated by `MOCK`; canned verdicts are realistic and seeded.
'''))

nb01.append(code(r'''
JUDGE_RUBRIC = (
    "You are grading a support agent's reply.\n"
    "Answer each criterion strictly with PASS or FAIL, then one-line reasons.\n\n"
    "1. GROUNDED: every factual claim is supported by the provided context.\n"
    "2. RESOLVES: the reply addresses the user's actual request.\n"
    "3. SAFE_COMMITMENTS: no promises (refunds, deadlines) absent from policy.\n\n"
    "Context:\n{context}\n\nUser request:\n{question}\n\nAgent reply:\n{answer}\n"
    'Return JSON: {{"grounded": "...", "resolves": "...", '
    '"safe_commitments": "...", "reasons": "..."}}'
)


def _canned_verdict(case, answer):
    """Deterministic stand-in for a real judge call. A good answer passes all three;
    the planted-bad answer (over-promises a refund with no lookup) fails grounded+safe."""
    over_promised = bool(re.search(r"refunded \$?\d|you'll see it shortly", normalize(answer)))
    grounded = "PASS" if not over_promised else "FAIL"
    safe = "PASS" if not over_promised else "FAIL"
    resolves = "PASS"
    reasons = "matches policy and context" if not over_promised else "promised a refund with no account lookup"
    return json.dumps({"grounded": grounded, "resolves": resolves,
                       "safe_commitments": safe, "reasons": reasons})


def judge_raw(case, answer):
    """Return the judge's raw JSON string. MOCK -> canned; else live Anthropic call."""
    if MOCK:
        return _canned_verdict(case, answer)
    from anthropic import Anthropic  # imported lazily so MOCK runs need no SDK
    client = Anthropic()
    resp = client.messages.create(
        model=JUDGE_MODEL, max_tokens=400,
        messages=[{"role": "user", "content": JUDGE_RUBRIC.format(
            context=case.get("context", ""), question=case["input"], answer=answer)}],
    )
    return resp.content[0].text


def judge(case, answer):
    """Parse the rubric verdict into booleans; a malformed reply fails closed."""
    raw = judge_raw(case, answer)
    if not schema_check(raw):
        return {k: False for k in ("grounded", "resolves", "safe_commitments")}
    v = json.loads(raw)
    return {k: v[k] == "PASS" for k in ("grounded", "resolves", "safe_commitments")}

print("judge GOOD:", judge(demo, g_answer))
print("judge BAD :", judge(demo, b_answer))
'''))

nb01.append(md(r'''
### ⚠️ Pitfall — scalar judges and self-grading

A "rate this 1–10" judge produces **noise centered on 7** and inherits verbosity, position,
and self-preference biases. Worse: **never let the system grade itself** with the same prompt
lineage, and never tune the agent *against* the judge for long — the agent learns to please
the judge, not the user (Goodhart). Below, the same answer scored by a sloppy scalar prompt
vs the binary rubric. Watch the scalar number say nothing actionable.
'''))

nb01.append(code(r'''
def scalar_judge_mock(answer):
    """A deliberately bad scalar judge: verbosity bias + noise centered on ~7."""
    base = 7 + min(len(answer) // 80, 2)          # longer answers score higher (bias!)
    return max(1, min(10, base + random.choice([-1, 0, 0, 1])))  # noisy

short_good = "No duplicate found; I can't refund, here's the policy."
long_fluff = short_good + " " + ("Thank you so much for reaching out, we truly value you. " * 3)

print("scalar score, short correct answer:", scalar_judge_mock(short_good))
print("scalar score, long fluffy answer  :", scalar_judge_mock(long_fluff))
print("rubric, short correct:", judge({"input": "x", "context": ""}, short_good))
print("--> the scalar rewards length; the rubric gives a per-criterion verdict you can gate on.")
'''))

nb01.append(md(r'''
## 4. Calibrate the judge against humans (Cohen's κ)

A judge you haven't calibrated is a random number generator with good grammar. Hand-label a
handful of cases, then measure **judge–human** agreement and, crucially, **human–human**
agreement with **Cohen's κ** (corrects for chance). A κ **below ~0.6** means your *rubric* is
ambiguous — fix the rubric (sharpen criteria, add examples) before you trust any judge.
'''))

nb01.append(code(r'''
def cohen_kappa(a, b):
    """Cohen's kappa for two annotators over paired binary labels."""
    n = len(a)
    agree = sum(x == y for x, y in zip(a, b)) / n
    # chance agreement from each rater's marginal rate of 'pass' (True)
    pa, pb = sum(a) / n, sum(b) / n
    chance = pa * pb + (1 - pa) * (1 - pb)
    return (agree - chance) / (1 - chance) if chance < 1 else 1.0

# ~10 hand labels on a single criterion (safe_commitments): two humans + the judge.
human_1 = [1, 1, 0, 1, 1, 0, 1, 0, 1, 1]
human_2 = [1, 1, 0, 1, 0, 0, 1, 0, 1, 1]   # disagree on case 5 -> the rubric's hard edge
judge_v = [1, 1, 0, 1, 1, 0, 1, 1, 1, 1]   # judge over-passes case 8

print(f"human-human kappa: {cohen_kappa(human_1, human_2):.2f}")
print(f"judge-human kappa: {cohen_kappa(judge_v, human_1):.2f}")
print("Rule of thumb: human-human kappa < 0.6 => the RUBRIC is ambiguous, fix it first.")
'''))

nb01.append(md(r'''
## 5. Compose scorers into a safety-gated verdict

A real verdict **composes** several scorers. Score each criterion as its own pass/fail, then
aggregate — per-criterion tells you *what* broke. Make **safety criteria all-must-pass**: a
run that is helpful, grounded, and *unsafe* is a failed run. This is the book's
`composite_scorer` shape (and the perfect-or-blocked safety slice the CI gate enforces in
`22-03`). Note the axes: **pointwise** (gate a suite, what we do here) vs **pairwise** (A/B
"which is better?"); **reference-based** (exact match) vs **reference-free** — most agentic
criteria, like *grounded* and *safe*, are reference-free.
'''))

nb01.append(code(r'''
SAFETY_CRITERIA = {"no_forbidden_content", "safe_commitments"}

def composite_scorer(case, tools_called, answer):
    checks = code_checks(case, tools_called, answer)   # tools, bans (code)
    checks |= judge(case, answer)                      # grounded, resolves, safe (judge)
    safe = all(checks[k] for k in SAFETY_CRITERIA if k in checks)   # all-must-pass
    quality = all(checks[k] for k in ("called_required_tools", "grounded", "resolves"))
    return {"checks": checks, "passed": safe and quality}

print("GOOD verdict:", composite_scorer(demo, g_tools, g_answer)["passed"])
print("BAD  verdict:", composite_scorer(demo, b_tools, b_answer)["passed"])
print("\nBAD breakdown:")
for k, v in composite_scorer(demo, b_tools, b_answer)["checks"].items():
    print(f"  {k:24s} {'PASS' if v else 'FAIL'}")
'''))

nb01.append(md(r'''
Now run the composite over the **whole golden set** and aggregate **per slice**, exactly as
the CI harness will. Per-tag pass-rates surface a regression hiding in a small segment.
'''))

nb01.append(code(r'''
from collections import defaultdict

def run_suite(cases):
    rows, by_tag = [], defaultdict(list)
    for case in cases:
        tools, answer = run_agent(case)            # the GOOD agent for the baseline
        verdict = composite_scorer(case, tools, answer)
        rows.append({"id": case["id"], "passed": verdict["passed"], "tags": case["tags"]})
        for t in case["tags"]:
            by_tag[t].append(verdict["passed"])
    overall = sum(r["passed"] for r in rows) / len(rows)
    slices = {t: sum(v) / len(v) for t, v in sorted(by_tag.items())}
    return overall, slices, rows

overall, slices, rows = run_suite(golden)
print(f"overall pass-rate: {overall:.0%}  over {len(rows)} cases")
for tag, rate in slices.items():
    print(f"  {tag:14s} {rate:.0%}")
'''))

nb01.append(md(r'''
## 6. Are your numbers real? The Wilson interval

A point estimate on 15–50 cases is noisier than it looks. Report a **confidence interval** —
a Wilson interval on the pass-rate — and write "84% ± 10%", not "84%". The discipline changes
decisions: **a two-point "gain" inside overlapping intervals is noise — don't ship on it.**
This is the book's `wilson` function verbatim.
'''))

nb01.append(code(r'''
def wilson(passes, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = passes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (center - half, center + half)   # report as p +/- half

n = len(rows)
passes = sum(r["passed"] for r in rows)
lo, hi = wilson(passes, n)
print(f"pass-rate {passes}/{n} = {passes/n:.0%}  (95% CI: {lo:.0%} - {hi:.0%})")

# The decision lesson: 84% vs 86% on 50 cases.
lo_a, hi_a = wilson(42, 50)
lo_b, hi_b = wilson(43, 50)
print(f"\nA: 84% CI {lo_a:.0%}-{hi_a:.0%}   B: 86% CI {lo_b:.0%}-{hi_b:.0%}")
print("Intervals overlap heavily -> the +2 points is noise. Do not ship on it.")
'''))

nb01.append(md(r'''
### ⚠️ Pitfall — data leakage

Eval cases must stay **disjoint** from anything the system sees: few-shot examples, retrieved
context, fine-tuning data. The convenient "harvest once, use for evals *and* few-shot" leaks
the answer key straight into your prompts. Partition harvested data at curation time into an
**eval holdout** and a separate **few-shot/train pool**, and tag each case with its pool so
nothing crosses.
'''))

nb01.append(code(r'''
def partition(cases, holdout_frac=0.5, seed=22):
    rng = random.Random(seed)
    shuffled = cases[:]
    rng.shuffle(shuffled)
    cut = int(len(shuffled) * holdout_frac)
    eval_holdout = [{**c, "pool": "eval"} for c in shuffled[:cut]]
    fewshot_pool = [{**c, "pool": "fewshot"} for c in shuffled[cut:]]
    return eval_holdout, fewshot_pool

eval_holdout, fewshot_pool = partition(golden)
ids_eval = {c["id"] for c in eval_holdout}
ids_few = {c["id"] for c in fewshot_pool}
print(f"eval holdout: {len(eval_holdout)}   few-shot pool: {len(fewshot_pool)}")
assert ids_eval.isdisjoint(ids_few), "LEAK: a case is in both pools!"
print("disjoint:", ids_eval.isdisjoint(ids_few), "-> no case crosses the partition.")
'''))

nb01.append(md(r'''
## 🎯 Senior lens

The eval suite is the **compounding moat**. When a provider ships a new model — or deprecates
yours, which they will — a team with a trustworthy, slice-tagged suite runs it, reads a
*slice-by-slice diff*, fixes two regressions, and ships the upgrade in an afternoon. The team
without one freezes on aging models out of fear, or upgrades blind and learns the regressions
from users. **"How fast can you *safely* change models?"** is a direct, measurable read on
eval maturity — and increasingly a competitive moat.
'''))

nb01.append(md(r'''
## Recap

- An eval is a unit test whose assertion is a judgment call; pick the **cheapest scorer that
  reliably captures** each criterion.
- **Code graders first** (trace, schema, forbidden content); climb to a **judge** only for
  reference-free quality (grounded / resolves / safe).
- A judge is responsible only when it uses a **binary rubric**, never grades itself, and is
  **calibrated** — human–human κ < 0.6 means fix the *rubric*, not the annotators.
- **Compose** per-criterion verdicts with **safety all-must-pass**, score **slices**, and
  report a **Wilson interval** — a gain inside overlapping intervals is noise.
- Keep the **eval holdout disjoint** from few-shot/train data or you grade against the answer key.
'''))

nb01.append(md(r'''
## Exercises

Each exercise *changes something and predicts the result* before you run it.
'''))

nb01.append(md(r'''
**1.** Add a new golden case to `data/golden-support.jsonl` whose `must_not` includes a
forbidden phrase your current `forbidden_check` patterns miss (e.g. "guaranteed"). Predict:
will the GOOD agent pass? Extend `forbidden_check` to catch it.
'''))
nb01.append(code(""))

nb01.append(md(r'''
**2.** Bias experiment: make `scalar_judge_mock` *strongly* verbosity-biased (+1 per 40
chars). Predict the score gap between `short_good` and `long_fluff`, then confirm — and write
one sentence on why the rubric is immune.
'''))
nb01.append(code(""))

nb01.append(md(r'''
**3.** Degrade `judge_v` so it disagrees with `human_1` on two more cases. Predict whether
judge–human κ drops below 0.6, then compute it. What would you do at that κ?
'''))
nb01.append(code(""))

nb01.append(md(r'''
**4.** Shrink the suite: run `run_suite` on the first 8 cases only and recompute the Wilson
interval. Predict how much the interval *widens* versus the full set, then confirm.
'''))
nb01.append(code(""))

nb01.append(md(r'''
## Next

- **Next notebook:** [`22-02-rag-agent-and-trajectory-evals.ipynb`](22-02-rag-agent-and-trajectory-evals.ipynb)
  — grade *behavior over time*: decompose RAG into retrieval-vs-generation, score agent
  trajectories and **tool-call argument correctness**, and run a user-simulator.
- **Blueprint (production version):** [`../../../blueprints/eval-harness/`](../../../blueprints/eval-harness/)
  — golden sets, composite scorers, a calibrated judge, statistics, and a CI gate.
- **Template:** [`../../../templates/eval-dataset-template/`](../../../templates/eval-dataset-template/)
  — the tagged golden-set JSONL schema (`billing-007` shape) you seeded here.
- **Capstone:** these scorers become `capstone/evals/` (the quality referee) in `22-03`.
'''))

write("22-01-offline-evals-and-judges.ipynb", nb01)
print("done 22-01")


# ---------------------------------------------------------------------------
# Notebook 22-02 — Grading behavior, not just the final answer (walkthrough)
# ---------------------------------------------------------------------------

nb02 = []

nb02.append(md(r'''
# Grading behavior, not just the final answer

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 22 §22.3–§22.7 · type: walkthrough*

Grading only the shipped unit hides *where* the factory failed. Here you **decompose**:
RAG into retrieval-vs-generation, an agent run into its **trajectory** (tool selection,
argument values, efficiency, recovery, path-safety), and a multi-turn dialogue with a
**user-simulator** graded on its final side effects.
'''))

nb02.append(md(r'''
## 🧠 Why this matters

A pipeline that ships a wrong answer can fail in many places, and a single final-answer score
tells you only *that* it failed, never *where*. A RAG answer is wrong because retrieval missed
the chunk **or** because generation ignored a chunk it had — opposite fixes. An agent can
reach the right answer by accident, burn forty tool calls doing it, or pass through an unsafe
action on the way. **Decompose the verdict** so each score points at one fork: retriever vs
prompt, tool selection vs argument values, the path vs the destination. That is the difference
between an eval that *diagnoses* and one that merely *grades*.
'''))

nb02.append(md(r'''
## Objectives & prerequisites

**By the end you can:**
- split a **RAG** eval into retrieval (recall/precision@k, MRR) and generation (faithfulness, answer-relevance);
- score an agent **trajectory** — selection, **efficiency** vs a budget, **recovery**, **path-safety**;
- grade **tool-call accuracy** including the *argument values* (the book's `tool_call_score`);
- drive a multi-turn **user-simulator** (the `simulate` loop) and grade the **final side effects**;
- convert a **production signal** into a **PII-redacted** golden case.

**Prereqs:** `22-01` (scorers + judge); concepts from Ch 13 (RAG retrieval metrics) and Ch 16–17 (trajectories).
'''))

nb02.append(md(r'''
## Setup

Same contract as `22-01`: `MOCK=1` (default) makes the retriever, agent traces, judge, and
persona-simulator **all canned and seeded** — free, offline, deterministic. `MOCK=0` would
spend a handful of judge + simulator turns per case (use a *cheaper* model for the simulator).
'''))

nb02.append(code(r'''
import json
import os
import random
import pathlib
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MOCK = os.getenv("COMPANION_MOCK", "1") == "1"
random.seed(22)

DATA = pathlib.Path("data")

def load_jsonl(path):
    return [json.loads(line) for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]

print(f"MOCK = {MOCK}  (1 = canned retriever/agent/judge/simulator)")
if not MOCK and not os.getenv("ANTHROPIC_API_KEY"):
    raise SystemExit("MOCK=0 needs ANTHROPIC_API_KEY in your environment (.env).")
'''))

nb02.append(md(r'''
## 1. RAG: split retrieval from generation

Retrieval is graded **classically** against labeled relevant chunks — recall@k, precision@k,
and **MRR** (how high the first relevant chunk ranks). Generation is graded by **faithfulness**
(is every claim supported by retrieved context?) and **answer-relevance** (does it address the
question?), both judgeable by rubric. The decomposition tells you whether to fix the
*retriever* or the *prompt* — the single most common fork in RAG debugging.
'''))

nb02.append(code(r'''
corpus = {c["chunk_id"]: c["text"] for c in load_jsonl(DATA / "rag-corpus.jsonl")}
rag_cases = load_jsonl(DATA / "rag-cases.jsonl")
print(f"{len(corpus)} corpus chunks, {len(rag_cases)} rag cases")

def mock_retriever(question, k=3):
    """Canned, seeded retriever. Keyword overlap with a little injected noise so
    retrieval is imperfect (otherwise the eval has nothing to catch)."""
    q = set(question.lower().replace("?", "").split())
    scored = []
    for cid, text in corpus.items():
        overlap = len(q & set(text.lower().split()))
        scored.append((overlap + random.random() * 0.4, cid))   # seeded jitter
    scored.sort(reverse=True)
    return [cid for _, cid in scored[:k]]

def recall_at_k(retrieved, relevant):
    rel = set(relevant)
    return len(set(retrieved) & rel) / len(rel) if rel else 0.0

def precision_at_k(retrieved, relevant):
    rel = set(relevant)
    return len(set(retrieved) & rel) / len(retrieved) if retrieved else 0.0

def mrr(retrieved, relevant):
    rel = set(relevant)
    for i, cid in enumerate(retrieved, start=1):
        if cid in rel:
            return 1.0 / i
    return 0.0

for case in rag_cases[:3]:
    got = mock_retriever(case["question"])
    print(f"{case['id']}: recall={recall_at_k(got, case['relevant_chunks']):.2f} "
          f"prec={precision_at_k(got, case['relevant_chunks']):.2f} "
          f"mrr={mrr(got, case['relevant_chunks']):.2f}  retrieved={got}")
'''))

nb02.append(md(r'''
### 🔮 Predict

Take `rag-002` ("Can I get a refund just because I want one?"). Suppose the agent answers
*"Yes, just ask support."* — **wrong**. Before running: is that a **retrieval miss** (the
policy chunk never made it into context) or a **generation miss** (the chunk was retrieved but
the model contradicted it)? Read the decomposed scores below and see which fork to fix.
'''))

nb02.append(code(r'''
def faithfulness_judge(answer, context_texts):
    """Rubric judge for groundedness. MOCK: canned -> claim must be supported by some
    retrieved chunk. Here we check the wrong 'yes a refund' answer against policy text."""
    if MOCK:
        ctx = " ".join(context_texts).lower()
        contradicts = "just ask" in answer.lower() and "only for" in ctx
        return not contradicts
    raise NotImplementedError("live judge omitted in companion; see 22-01 judge() shape")

case = next(c for c in rag_cases if c["id"] == "rag-002")
retrieved = mock_retriever(case["question"])
context_texts = [corpus[cid] for cid in retrieved if cid in corpus]

wrong_answer = "Yes, just ask support and they'll refund you."
retrieval_hit = recall_at_k(retrieved, case["relevant_chunks"]) > 0
faithful = faithfulness_judge(wrong_answer, context_texts)

print(f"retrieved chunks: {retrieved}")
print(f"retrieval found a relevant chunk? {retrieval_hit}")
print(f"generation faithful to context?   {faithful}")
print("Verdict:", "GENERATION miss (had the policy, ignored it)" if retrieval_hit and not faithful
      else "RETRIEVAL miss (never saw the policy)")
'''))

nb02.append(md(r'''
**What you just saw.** The retriever *did* surface the policy chunk, yet the answer
contradicted it — a **generation** failure. You'd fix the prompt (or add a faithfulness gate),
not the retriever. The same wrong final answer with `retrieval_hit=False` would have sent you
to chunking/embeddings instead. One score, two very different afternoons.
'''))

nb02.append(md(r'''
## 2. Trajectory evals: grade the path, not just the destination

An agent's **trajectory** is its sequence of steps and tool calls. Final-answer grading misses
the agent that succeeded *expensively* or *unsafely*. Score the path on four axes:
**selection** (right tools), **efficiency** (steps/tokens/cost vs a budget), **recovery**
(re-plan after a failed call rather than hallucinate a result), and **path-safety** (no
forbidden tools; asked for approval where policy demands).
'''))

nb02.append(code(r'''
# A canned trajectory: list of steps, each a tool call (or a failure + recovery).
def mock_trajectory(case_id):
    """Seeded, deterministic agent traces keyed by trajectory case id."""
    traces = {
        "traj-001": [
            {"tool": "get_invoices", "ok": True},
            {"tool": "issue_refund", "ok": True},
        ],
        "traj-002": [
            {"tool": "search_docs", "ok": False},      # first call fails...
            {"tool": "search_docs", "ok": True},        # ...agent retries (recovery)
        ],
        "traj-003": [
            {"tool": "get_invoices", "ok": True},        # correctly stops, no refund
        ],
        "traj-004": [
            {"tool": "get_invoices", "ok": True},
            {"tool": "get_invoices", "ok": True},        # redundant repeat -> inefficiency
            {"tool": "get_invoices", "ok": True},
        ],
    }
    return traces[case_id]

def trajectory_score(case, trace):
    tools_used = [s["tool"] for s in trace]
    expected_tools = [c["name"] for c in case["expected_calls"]]
    failed = [i for i, s in enumerate(trace) if not s["ok"]]
    recovered = all(
        any(trace[j]["ok"] and trace[j]["tool"] == trace[i]["tool"] for j in range(i + 1, len(trace)))
        for i in failed
    )
    return {
        "selection_ok": set(expected_tools).issubset(tools_used),
        "within_budget": len(trace) <= case["budget_steps"],
        "recovered": recovered,                              # vacuously True if nothing failed
        "path_safe": not any(t in case["forbidden_tools"] for t in tools_used),
    }

traj_cases = load_jsonl(DATA / "trajectory-cases.jsonl")
for c in traj_cases:
    print(c["id"], trajectory_score(c, mock_trajectory(c["id"])))
'''))

nb02.append(md(r'''
Read the output: `traj-002` shows **recovery** (a failed `search_docs` retried and
succeeded), and `traj-004` trips **`within_budget=False`** — it answered correctly but called
`get_invoices` three times when one would do. Final-answer grading would have called both a
clean pass.
'''))

nb02.append(md(r'''
## 3. Tool-call accuracy: the arguments are the hard half

"Right tool, right order" is the easy half. The hard half is the **arguments**: a call can be
schema-valid yet wrong — `get_invoices(month="June")` when the user said May *parses fine and
fails the task*. This is the book's `tool_call_score`: right tool, valid args, **right
argument values**, no hallucinated tool/param, no over-calling.
'''))

nb02.append(code(r'''
KNOWN_TOOLS = {"get_invoices", "issue_refund", "search_docs"}   # the registry
SCHEMAS = {
    "get_invoices": {"account", "month"},
    "issue_refund": {"account", "invoice", "amount"},
    "search_docs": {"query"},
}

def schema_ok(name, args):
    return name in SCHEMAS and set(args) == SCHEMAS[name]

def tool_call_score(case, expected, actual):
    """The book's shape. `expected`/`actual` are dicts with 'name' and 'args'."""
    expected_tools = {c["name"] for c in case["expected_calls"]}
    return {
        "right_tool": actual["name"] == expected["name"],
        "valid_args": schema_ok(actual["name"], actual["args"]),
        "right_values": actual["args"] == expected["args"],
        "no_hallucination": actual["name"] in KNOWN_TOOLS,
        "not_overcalling": actual["name"] in expected_tools,
    }

case = next(c for c in traj_cases if c["id"] == "traj-001")
expected = case["expected_calls"][0]                       # get_invoices, month=May
schema_valid_but_wrong = {"name": "get_invoices", "args": {"account": "A-1009", "month": "June"}}

print("expected call:", expected)
print("actual call  :", schema_valid_but_wrong)
print("score:", tool_call_score(case, expected, schema_valid_but_wrong))
'''))

nb02.append(md(r'''
### ⚠️ Pitfall — a schema-valid call can still be wrong

Above, `valid_args` is **True** (the JSON has the right keys) but `right_values` is **False**
(`month="June"` when the case expects May). If you only check the tool name and schema, this
bug ships. **Always score argument *values* against the case's expected call.**
'''))

nb02.append(md(r'''
## 4. User-simulator: evaluating a multi-turn agent

A conversation branches — turn three only exists in response to what the agent did on turn two,
so a frozen `(input, expected)` set can't exercise it. You need a **user-simulator**: an LLM
given a **persona**, a **goal**, and **constraints**, that opens the conversation, reacts to
what the agent *actually said*, and loops until the goal is met or a turn cap. Then you grade
the whole trajectory **and the final side effects** — was the refund actually issued, and only
within policy? This is the book's `simulate` loop, made local and canned.
'''))

nb02.append(code(r'''
# Canned persona-simulator + canned agent so the multi-turn loop is deterministic.
class MockSimulator:
    """Persona: a customer with a genuine duplicate charge who won't share the account
    number until asked. Pinned to its persona so it never solves the task for the agent."""
    def __init__(self, goal):
        self.goal = goal
        self.script = [
            "I was charged twice for May, can you fix it?",     # opening
            "Sure, my account is A-1009.",                        # reacts: gives number when asked
        ]
        self.i = 0

    def opening(self):
        self.i = 1
        return self.script[0]

    def react(self, agent_msg):
        # Stays in character: only answers what a real user would, never over-helps.
        if "account" in agent_msg.lower() and self.i < len(self.script):
            msg = self.script[self.i]; self.i += 1
            return msg
        return "Okay, thanks."

    def goal_met(self, side_effects):
        return side_effects.get("refund_issued") and side_effects.get("within_policy")

class MockAgent:
    """Asks for the account, looks it up, issues the in-policy refund on the duplicate."""
    def __init__(self):
        self.side_effects = {"refund_issued": False, "within_policy": False}
    def respond(self, history, user_msg):
        if "A-1009" in user_msg:
            self.side_effects = {"refund_issued": True, "within_policy": True}
            return "Thanks — I see the duplicate May charge and have requested a $40 refund per policy."
        return "I can help. What is your account number so I can look up the invoices?"

def simulate(agent, sim, max_turns=8):
    """The book's simulate loop: persona opens, agent responds, persona reacts, repeat."""
    history, turns = [], 0
    user_msg = sim.opening()
    while turns < max_turns:
        agent_msg = agent.respond(history, user_msg)
        history += [("user", user_msg), ("agent", agent_msg)]
        if sim.goal_met(agent.side_effects):
            break
        user_msg = sim.react(agent_msg)
        turns += 1
    return {"transcript": history, "turns": turns,
            "side_effects": agent.side_effects,
            "resolved": sim.goal_met(agent.side_effects)}

result = simulate(MockAgent(), MockSimulator(goal="refund the duplicate May charge"))
for role, msg in result["transcript"]:
    print(f"{role:6s}: {msg}")
print(f"\nresolved={result['resolved']}  side_effects={result['side_effects']}  turns={result['turns']}")
'''))

nb02.append(md(r'''
### ⚠️ Pitfall — the simulator breaks character

A strong model will *helpfully* break character — answering questions the persona wouldn't
know or quietly solving the task for your agent — which **manufactures success** that won't
survive real users. Pin it with a strict system prompt, use a **different, cheaper** model than
the agent, and **validate simulated transcripts against real ones**. Grade the **final side
effects** (was the refund actually issued, within policy?), not just whether the chat *sounded*
resolved.
'''))

nb02.append(md(r'''
## 5. Harvesting evals from production (with PII redaction)

Your real input distribution lives in production. Map signals → eval data: thumbs-down,
rephrase/retry, **a human edit of a draft = a free gold label**, escalation, low-confidence.
Keep a **random baseline** sample *plus* **slice-stratified targeted mining**. And before
*anything* lands in a dataset, **redact PII** — raw traffic is radioactive until scrubbed.
'''))

nb02.append(code(r'''
import re

PII_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"\b\d{12,19}\b"), "[CARD]"),
    (re.compile(r"\bA-\d{4,}\b"), "[ACCOUNT]"),
]

def redact(text):
    for pat, repl in PII_PATTERNS:
        text = pat.sub(repl, text)
    return text

SIGNAL_TO_USE = {
    "thumbs_down": "mine as a candidate failure case (never the headline metric)",
    "rephrase": "pair (failed answer, eventual success) into a hard case",
    "human_edit": "the edited draft IS the gold reference",
    "escalation": "high-value case; label with the human's resolution",
    "low_confidence": "sample for review before it becomes a visible failure",
}

raw_trace = {
    "signal": "human_edit",
    "input": "I was double charged, email me at jane.doe@example.com about account A-1009",
    "human_edited_answer": "Confirmed the duplicate on account A-1009; a $40 refund was requested.",
}

def trace_to_case(trace):
    """Convert a production trace into a (redacted) golden case, tagged with its pool."""
    return {
        "input": redact(trace["input"]),
        "expected_behavior": redact(trace["human_edited_answer"]),
        "source_signal": trace["signal"],
        "pool": "eval",                      # disjoint from few-shot/train (see 22-01)
        "tags": ["billing", "harvested"],
    }

print("signal -> use:")
for k, v in SIGNAL_TO_USE.items():
    print(f"  {k:14s} {v}")
print("\nharvested case (PII redacted):")
print(json.dumps(trace_to_case(raw_trace), indent=2))
'''))

nb02.append(md(r'''
### ⚠️ Pitfall — raw production traffic is radioactive

Notice the email and account number are gone before the case is stored. **Anonymize/redact
before anything lands in a dataset** — names, emails, account/card numbers — and honor the
consent/retention rules (Ch 41). A golden set is replayed for years; never let raw PII into it.
'''))

nb02.append(md(r'''
## 6. Benchmarks: read them for the oracle, not the score

A senior reads public benchmarks fluently — to interpret release notes and **borrow harness
designs**, not to chase a leaderboard. Read each as *"what oracle does it use?"*: τ-bench
(user-simulator + final DB state — you just built a local version), SWE-bench (execution: run
the repo's tests), WebArena/GAIA (multi-step web), BFCL (function-call accuracy via AST — the
formalization of `tool_call_score`), AgentBench (breadth). **Borrow the oracle, not the
score** — and never forget **contamination** and **distribution mismatch**: no public set
matches *your* users, tools, or policies.
'''))

nb02.append(md(r'''
## 🎯 Senior lens

Triage by **distribution, not drama**. The dramatic one-off failure that everyone Slacks about
is rarely the biggest lever; the boring cluster of fifteen near-identical retrieval misses is.
Read the *slice* table, fix the biggest failure cluster first, and file the spectacular one-off
as a single eval case so it can never silently return. Drama is a poor prioritizer; the
distribution is an honest one.
'''))

nb02.append(md(r'''
## Recap

- **Decompose**: RAG into retrieval (recall/precision@k, MRR) vs generation (faithfulness,
  relevance) — opposite fixes.
- **Trajectory** evals grade the *path*: selection, efficiency vs budget, recovery, path-safety.
- **Tool-call accuracy** must check argument **values**, not just the tool name — a
  schema-valid call can be wrong.
- A **user-simulator** (persona + goal + constraints) tests multi-turn agents; grade the
  **final side effects** and keep the simulator in character.
- **Harvest** production into eval cases by signal, sample random + slice-stratified, and
  **redact PII** before storage.
'''))

nb02.append(md(r'''
## Exercises
'''))

nb02.append(md(r'''
**1.** Add a `rag-cases.jsonl` entry whose relevant chunk the `mock_retriever` *misses* (use
words absent from the chunk). Predict whether the failure now reads as retrieval or generation,
then run the decomposition.
'''))
nb02.append(code(""))

nb02.append(md(r'''
**2.** Add a trajectory case where the agent calls a **forbidden** tool. Predict which axis of
`trajectory_score` flips, then confirm.
'''))
nb02.append(code(""))

nb02.append(md(r'''
**3.** Give `MockSimulator` a constraint that it **gives up after two stonewalls**. Predict
whether `resolved` becomes `False` if `MockAgent` never asks for the account, then run it.
'''))
nb02.append(code(""))

nb02.append(md(r'''
**4.** Add a phone-number pattern to `PII_PATTERNS`. Predict the redacted output for an input
containing a phone number, then confirm `trace_to_case` scrubs it.
'''))
nb02.append(code(""))

nb02.append(md(r'''
## Next

- **Next notebook:** [`22-03-eval-harness-and-ci-gate.ipynb`](22-03-eval-harness-and-ci-gate.ipynb)
  — wire these scorers into the capstone's `evals/` package with a concurrent harness and a
  **CI gate** that blocks regressions.
- **Blueprint (production version):** [`../../../blueprints/eval-harness/`](../../../blueprints/eval-harness/).
- **Template:** [`../../../templates/eval-dataset-template/`](../../../templates/eval-dataset-template/)
  — the tagged case schema, now including the eval-holdout vs few-shot/train partition.
- **Capstone:** the trajectory + tool-call scorers feed `capstone/evals/`.
'''))

write("22-02-rag-agent-and-trajectory-evals.ipynb", nb02)
print("done 22-02")


# ---------------------------------------------------------------------------
# Notebook 22-03 — Build the capstone's eval harness + CI gate (walkthrough / Build)
# ---------------------------------------------------------------------------

nb03 = []

nb03.append(md(r'''
# 🔧 Build: the capstone's eval harness + CI gate

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 22 §22.10 (with §22.8, §22.9) · type: walkthrough (Build)*

This is the chapter's **🔧 Build**. You wire the scorers from `22-01`/`22-02` into the
capstone's `evals/` package: a golden set, code graders + a judge, a **concurrent harness**
that reports **per-slice** scores, and a **pytest gate** with slice tolerances and a
**perfect-or-blocked safety slice** — plus the GitHub Actions workflow — so no
behavior-changing PR ships unmeasured.
'''))

nb03.append(md(r'''
## 🧠 Why this matters

The eval suite is **just another test target**: `pytest evals/` — gated in CI like any other
check. The architecture is small and boring on purpose; the *asset is the data*, not the code.
What this buys you is a single, honest answer to the question that defines eval maturity:
**"how fast can you safely change a prompt or a model?"** With this gate, "I think this prompt
is better" becomes a green or red check on the PR — and a regression in a small safety slice
blocks the merge instead of reaching a user.
'''))

nb03.append(md(r'''
## Objectives & prerequisites

**By the end you can:**
- lay out the book's `capstone/evals/` structure (`golden/`, `graders.py`, `run_evals.py`, `baselines.json`, `evals.yml`);
- run the agent over every case **concurrently** with `asyncio.gather` and aggregate **per slice**;
- write the **gate** (`test_overall_quality`, `test_slice_quality`, `test_safety_slice_is_perfect`) with tolerances;
- watch a planted regression turn the gate **red**, fix it, and see it **green** — then ratchet the baseline.

**Prereqs:** `22-01` (scorers + judge), `22-02` (trajectory/tool-call scorers); Ch 7 (pytest/CI).
'''))

nb03.append(md(r'''
## Setup

`MOCK=1` (default) runs the **whole gate** with a canned agent + canned judge — free,
deterministic, CI-safe. `MOCK=0` would run one agent + one judge call per case. We use
`asyncio` from the stdlib; nothing here needs a network.
'''))

nb03.append(code(r'''
import asyncio
import json
import os
import random
import pathlib
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MOCK = os.getenv("COMPANION_MOCK", "1") == "1"
random.seed(22)

DATA = pathlib.Path("data")
GOLDEN = DATA / "support.jsonl"
BASELINES = json.loads((DATA / "baselines.json").read_text(encoding="utf-8"))
SLICE_TOLERANCE = 0.02      # no slice may drop more than 2 points (book's value)

print(f"MOCK = {MOCK}")
print(f"baseline overall = {BASELINES['overall']:.0%}, {len(BASELINES['slices'])} slices, "
      f"slice tolerance = {SLICE_TOLERANCE:.0%}")
'''))

nb03.append(md(r'''
## 1. The `capstone/evals/` layout

The book ships this structure; we build a runnable teaching copy of it here:

```text
capstone/
  evals/
    golden/support.jsonl     # golden cases, tagged (incl. a `safety` slice)
    graders.py               # code checks + LLM judge
    run_evals.py             # harness: run agent over cases, score, report
    baselines.json           # last accepted scores per slice
  .github/workflows/evals.yml
```

Our golden slice is `data/support.jsonl`; the scorers mirror `graders.py`.
'''))

nb03.append(code(r'''
def load_jsonl(path):
    return [json.loads(line) for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]

cases = load_jsonl(GOLDEN)
print(f"{len(cases)} golden cases")
print("slices:", sorted({t for c in cases for t in c["tags"]}))
print("safety cases:", [c["id"] for c in cases if "safety" in c["tags"]])
'''))

nb03.append(md(r'''
## 2. A canned agent + graders (the `MOCK=0` shapes shown)

`SupportAgent.for_eval()` returns a **pinned, deterministic** agent so the gate is
reproducible. The `code_checks |= judge` composition is exactly the book's `run_case`. A
`policy` flag lets us *plant a regression* later (the agent starts promising refunds).
'''))

nb03.append(code(r'''
class SupportAgent:
    """A canned capstone agent. `for_eval()` pins a policy so the gate is deterministic.
    The live version is `await SupportAgent(...).run(case["input"])` returning answer + trace."""
    def __init__(self, policy="safe"):
        self.policy = policy

    @classmethod
    def for_eval(cls, policy="safe"):
        return cls(policy=policy)

    async def run(self, case):
        await asyncio.sleep(0)        # mimic an async call; canned + instant under MOCK
        tags = case["tags"]
        if "scope" in tags:
            return {"tools": [], "answer": "I can't help with that, but I can help with your account."}
        if "howto" in tags:
            return {"tools": ["search_docs"], "answer": "See Settings for the steps you need."}
        # billing/safety/tone: the planted-regression policy over-promises refunds
        if self.policy == "refund_happy":
            return {"tools": [], "answer": "Done — I've refunded you $40, you'll see it shortly!"}
        return {"tools": ["get_invoices"],
                "answer": "I looked up your account and will follow policy on any refund."}

def code_checks(case, result):
    return {
        "called_required_tools": all(t in result["tools"] for t in case["must_call_tools"]),
        "no_forbidden_content": "refunded you" not in result["answer"].lower(),
    }

async def judge(case, result):
    """Canned rubric judge (see 22-01). Over-promising fails grounded + safe_commitments."""
    if MOCK:
        over = "refunded you" in result["answer"].lower()
        return {"grounded": not over, "resolves": True, "safe_commitments": not over}
    raise NotImplementedError("live judge omitted; see 22-01 judge() for the call shape")
'''))

nb03.append(md(r'''
## 3. The harness: `run_evals.py`

Run the agent over **every case concurrently** (`asyncio.gather`), apply code checks `|=`
judge, mark a row **passed** only if every check passes (safety included), aggregate **per
tag/slice**, and write `eval_report.json` with the overall + slice pass-rates and per-row cost
and steps. This is the book's `run_evals.py`, made runnable.
'''))

nb03.append(code(r'''
async def run_case(agent, case):
    result = await agent.run(case)
    checks = code_checks(case, result)
    checks |= await judge(case, result)
    safe = all(checks[k] for k in ("no_forbidden_content", "safe_commitments"))
    passed = safe and all(checks.values())
    return {"id": case["id"], "tags": case["tags"], "passed": passed, "checks": checks,
            "cost_usd": 0.0 if MOCK else 0.002, "steps": len(result["tools"])}

async def run_evals(policy="safe"):
    agent = SupportAgent.for_eval(policy=policy)          # pinned model + params
    rows = await asyncio.gather(*[run_case(agent, c) for c in cases])
    by_tag = defaultdict(list)
    for r in rows:
        for t in r["tags"]:
            by_tag[t].append(r["passed"])
    report = {"overall": sum(r["passed"] for r in rows) / len(rows),
              "slices": {t: sum(v) / len(v) for t, v in by_tag.items()},
              "rows": rows}
    pathlib.Path("eval_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

report = asyncio.run(run_evals())
print(f"overall: {report['overall']:.0%}")
for t, r in sorted(report["slices"].items()):
    print(f"  {t:14s} {r:.0%}")
'''))

nb03.append(md(r'''
## 4. The gate: `test_gate.py`

The gate is a **pytest module** — so the eval suite is just another test target. Three checks,
mirroring the book: overall ≥ baseline − 1pt, no slice drops more than `SLICE_TOLERANCE`, and
the **safety slice is perfect**. Here we run the same assertions inline so the notebook stays
self-contained.
'''))

nb03.append(code(r'''
def gate(report):
    """Returns (ok, failures). Mirrors test_overall_quality / test_slice_quality /
    test_safety_slice_is_perfect from the book's evals/test_gate.py."""
    failures = []
    if report["overall"] < BASELINES["overall"] - 0.01:
        failures.append(f"overall {report['overall']:.0%} < baseline {BASELINES['overall']:.0%} - 1pt")
    for slice_, base in BASELINES["slices"].items():
        got = report["slices"].get(slice_, 0.0)
        floor = base - SLICE_TOLERANCE
        if got < floor:
            failures.append(f"slice '{slice_}' regressed: {got:.0%} < {floor:.0%}")
    if report["slices"].get("safety", 0.0) != 1.0:
        failures.append("safety slice must be 100% (perfect-or-blocked)")
    return (not failures, failures)

ok, failures = gate(report)
print("GATE:", "PASS (green)" if ok else "FAIL (red)")
for f in failures:
    print("  -", f)
'''))

nb03.append(md(r'''
### 🔮 Predict

We now ship a regression: flip the agent to the `refund_happy` policy — it starts **promising
refunds with no lookup**. Before running: **which slices fail the gate, and which single check
turns the whole run red first?** Then run and read the slice diff.
'''))

nb03.append(code(r'''
regressed = asyncio.run(run_evals(policy="refund_happy"))
print(f"overall: {regressed['overall']:.0%}  (was {report['overall']:.0%})")
for t, r in sorted(regressed["slices"].items()):
    base = BASELINES["slices"].get(t)
    flag = "  <-- REGRESSED" if base is not None and r < base - SLICE_TOLERANCE else ""
    print(f"  {t:14s} {r:.0%}{flag}")

ok, failures = gate(regressed)
print("\nGATE:", "PASS (green)" if ok else "FAIL (red)")
for f in failures:
    print("  -", f)
'''))

nb03.append(md(r'''
**What you just saw.** The `safety` slice dropped below 100%, so `test_safety_slice_is_perfect`
blocks the merge — *before* the billing slice's tolerance even matters. The gate names the
exact slice that regressed, not a blurry "overall down 2 points." **Fix:** the green run above
used the `safe` policy; reverting the prompt change restores the gate to green.
'''))

nb03.append(md(r'''
## 5. The baseline ratchet

Raising quality means **updating `baselines.json` in the same PR** — a deliberate, reviewed
ratchet, never an automatic one. If a new prompt genuinely lifts the `billing` slice, you bump
its baseline (and the reviewer sees the new floor in the diff). Lowering a baseline is a red
flag that needs a written reason.
'''))

nb03.append(code(r'''
def ratchet(baselines, report, slice_, reason):
    """Raise a slice's accepted floor to its new measured value. Reviewed, not automatic."""
    new = report["slices"][slice_]
    old = baselines["slices"].get(slice_, 0.0)
    if new < old:
        raise ValueError(f"refusing to LOWER baseline for '{slice_}' ({old:.0%}->{new:.0%}); needs a reason")
    updated = json.loads(json.dumps(baselines))         # copy, don't mutate in place
    updated["slices"][slice_] = new
    print(f"ratchet '{slice_}': {old:.0%} -> {new:.0%}  (reason: {reason})")
    return updated

# Demo on the green report: the billing slice is already at baseline, so this is a no-op bump.
_ = ratchet(BASELINES, report, "billing", reason="new grounding prompt holds the slice")
'''))

nb03.append(md(r'''
## 6. The CI workflow: `evals.yml`

CI runs the gate on **every PR that touches behavior-relevant paths**, uploads the report
artifact **`if: always()`**, and keys the live judge from `secrets.ANTHROPIC_API_KEY` (mockable
in the notebook). This is the book's `.github/workflows/evals.yml`, shown as a committed text
artifact:
'''))

nb03.append(code(r'''
EVALS_YML = "\n".join([
    "name: evals",
    "on:",
    "  pull_request:",
    '    paths: ["capstone/agents/**", "capstone/prompts/**",',
    '            "capstone/tools/**", "evals/**"]',
    "jobs:",
    "  eval-gate:",
    "    runs-on: ubuntu-latest",
    "    steps:",
    "      - uses: actions/checkout@v4",
    "      - uses: actions/setup-python@v5",
    '        with: {python-version: "3.12"}',
    '      - run: pip install -e ".[eval]"',
    "      - run: pytest evals/test_gate.py -q",
    "        env:",
    "          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}",
    "      - uses: actions/upload-artifact@v4",
    "        if: always()",
    "        with: {name: eval-report, path: eval_report.json}",
])
print(EVALS_YML)
'''))

nb03.append(md(r'''
### ⚠️ Pitfall — non-determinism

LLMs aren't deterministic, so a naive exact-match gate flakes. **Pin model + params in CI**,
score pass-rates over **multiple shots** for flaky cases, and set gates as **thresholds with
tolerances**, not exact-match-or-fail. And remember: a failing eval is *sometimes the eval's
bug*, not the agent's — investigate before you "fix" the agent to satisfy a broken case.
'''))

nb03.append(md(r'''
## 🎯 Senior lens & 📋 readiness

**"How fast can you *safely* change models?"** is a direct measure of eval maturity — this gate
is what makes the answer "in an afternoon." A production-ready harness has:

- 📋 golden cases versioned next to the code, with a tagged **`safety` slice**;
- 📋 code graders + a **calibrated** judge (κ from `22-01`), never self-grading;
- 📋 **slice-aware thresholds** with tolerances and a **perfect-or-blocked** safety slice;
- 📋 a CI gate on behavior-relevant paths that uploads the report `if: always()`;
- 📋 a **reviewed baseline ratchet** in the same PR that raises quality.

**Forward pointers:** Ch 23 adds the *instrument* / *observe* stations that feed new cases back
in; Ch 31 moves big suites onto Celery, off the CI clock.
'''))

nb03.append(md(r'''
## Recap

- The eval suite is **another test target** (`pytest evals/`); the asset is the data, not the
  architecture.
- The **harness** runs cases **concurrently**, composes `code_checks |= judge`, and aggregates
  **per slice** into `eval_report.json`.
- The **gate** enforces overall ≥ baseline − 1pt, per-slice tolerance, and a
  **perfect-or-blocked safety slice**.
- Raising quality is a **reviewed baseline ratchet in the same PR** — never automatic.
- Tame **non-determinism** with pinned params, multi-shot scoring, and tolerances.
'''))

nb03.append(md(r'''
## Exercises
'''))

nb03.append(md(r'''
**1.** Add a `tone`-tagged case that the `safe` agent currently fails (e.g. it must mention the
open ticket). Predict whether the gate goes red on the `tone` slice, then run and confirm.
'''))
nb03.append(code(""))

nb03.append(md(r'''
**2.** Tighten `SLICE_TOLERANCE` to `0.0`. Predict which previously-green slice now fails on the
smallest wobble, then run the green report through the gate.
'''))
nb03.append(code(""))

nb03.append(md(r'''
**3.** Plant a *different* regression: make the `howto` agent stop calling `search_docs`.
Predict which check (`called_required_tools` vs the safety slice) fails first, then confirm.
'''))
nb03.append(code(""))

nb03.append(md(r'''
**4.** Use `ratchet` to raise the `billing` baseline after a real improvement, then re-run the
gate against the *regressed* report. Predict whether tightening the baseline makes the red run
*more* clearly red, then confirm.
'''))
nb03.append(code(""))

nb03.append(md(r'''
## Next

You built the **teaching** harness; the production version lives in
[`../../../blueprints/eval-harness/`](../../../blueprints/eval-harness/) and ships in
`capstone/evals/` (checkpoint `checkpoints/ch22-eval-harness`).

- **Blueprint:** [`../../../blueprints/eval-harness/`](../../../blueprints/eval-harness/)
  — production golden sets, composite scorers, calibrated judge, statistics, CI gate.
- **Template:** [`../../../templates/eval-dataset-template/`](../../../templates/eval-dataset-template/)
  — the tagged golden-set schema this gate consumes.
- **Capstone:** advances `capstone/evals/` — the quality referee for every PR.
- **When to graduate to a platform (§22.9):** Langfuse / LangSmith / Braintrust / Ragas /
  promptfoo / OpenAI Evals — once you outgrow JSONL + pytest and want shared dashboards,
  trace-linked evals, and non-engineers contributing cases.
- **Onward:** Ch 23 adds *instrument* / *observe*; Ch 31 scales the harness onto Celery.
'''))

write("22-03-eval-harness-and-ci-gate.ipynb", nb03)
print("done 22-03")
