"""Generate 17-01-when-and-which-topology.ipynb (concept-lab).

This builder writes a valid nbformat-4 notebook. Outputs are kept empty and
execution_count null per NOTEBOOK-STANDARDS. Run, then delete this builder.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "17-01-when-and-which-topology.ipynb")


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
    # Each element is one logical line; we add trailing newlines to all but last,
    # matching how Jupyter stores `source` as a list of lines.
    flat = []
    for block in lines:
        flat.extend(block.split("\n"))
    out = []
    for i, line in enumerate(flat):
        if i < len(flat) - 1:
            out.append(line + "\n")
        else:
            out.append(line)
    return out


cells = []

# 1. Title + header -----------------------------------------------------------
cells.append(md(
    "# One agent or four? Topologies and handoffs\n",
    "\n",
    "> \U0001F4D3 *Companion to* **Modern Agentic AI Engineer** *· Ch 17 §17.1–§17.3 · type: concept-lab*\n",
    "\n",
    "**The promise:** by the end you can decide *whether* to split one agent into a team, "
    "and *which* topology fits — by quantifying the costs a slick demo hides.",
))

# 2. Why this matters ---------------------------------------------------------
cells.append(md(
    "## \U0001F9E0 Why this matters\n",
    "\n",
    "A multi-agent system *is* a distributed system. Once one agent works, the temptation to "
    "add a researcher, a writer, a critic, and a manager arrives on schedule — it demos "
    "beautifully and flatters the intuition that intelligence scales like an org chart.\n",
    "\n",
    "But every hop adds a full model call of latency and cost, errors **compound** across "
    "handoffs, and shared state introduces races. Most teams reach for a team too soon. This "
    "lab makes the counter-forces *tangible* so you choose a topology on purpose — not "
    "because four boxes look more capable than one.",
))

# 3. Objectives + prereqs -----------------------------------------------------
cells.append(md(
    "## Objectives & prereqs\n",
    "\n",
    "**By the end you can:**\n",
    "- Justify every agent with a *named* force (context isolation, specialization, "
    "parallelism, privilege separation) — or admit there isn't one.\n",
    "- Compute how reliability compounds across handoffs and pick a topology accordingly.\n",
    "- Write a `Handoff` that doesn't silently drop the one fact that mattered.\n",
    "\n",
    "**Prereqs:** Ch 16 (reasoning patterns, `RunBudget`); Ch 8 (lost-in-the-middle / "
    "context). No API key and no network needed — this lab is offline by design.",
))

# 4. Setup --------------------------------------------------------------------
cells.append(code(
    "# Setup: stdlib + pydantic only. No API key required.\n",
    "import os\n",
    "import random\n",
    "from dataclasses import dataclass, field\n",
    "\n",
    "from dotenv import load_dotenv\n",
    "from pydantic import BaseModel, ValidationError\n",
    "\n",
    "load_dotenv()  # picks up a .env if you have one; nothing here needs it\n",
    "\n",
    "# MOCK=1 (default) keeps everything offline and deterministic. This concept-lab\n",
    "# never makes a live call even with MOCK=0 — the lesson is structural, not API-bound.\n",
    "MOCK = os.getenv(\"COMPANION_MOCK\", \"1\") == \"1\"\n",
    "\n",
    "SEED = 17\n",
    "random.seed(SEED)  # any stochastic demo below is reproducible\n",
    "\n",
    "print(f\"MOCK={MOCK}  (offline concept-lab; no keys, no spend)\")",
))

# 5. Body ---------------------------------------------------------------------
# 5a. mental model
cells.append(md(
    "## \U0001F9E0 Mental model: an agent is an employee\n",
    "\n",
    "Designing a multi-agent system is **organization design**. An agent is an employee "
    "defined by three things:\n",
    "\n",
    "| Employee | Agent |\n",
    "|---|---|\n",
    "| Job description | system prompt |\n",
    "| Skills | tools |\n",
    "| Need-to-know access | context + permissions |\n",
    "\n",
    "You hire a second person only when one person *genuinely cannot do the job* — too much "
    "to hold in their head, conflicting roles, or work that must happen in parallel. And like "
    "real orgs, every hire adds communication overhead that grows faster than headcount.",
))

cells.append(code(
    "# Encode the 'employee' framing as data so we can reason about a candidate team.\n",
    "@dataclass\n",
    "class AgentSpec:\n",
    "    role: str\n",
    "    job_description: str   # system prompt, in one line\n",
    "    skills: list           # tools\n",
    "    need_to_know: str      # the slice of context this role actually needs\n",
    "\n",
    "candidate_team = [\n",
    "    AgentSpec(\"researcher\", \"Find and cite facts from company docs\",\n",
    "              [\"search_docs\"], \"the question + the doc base\"),\n",
    "    AgentSpec(\"writer\", \"Turn notes into a polished brief\",\n",
    "              [], \"the research notes only\"),\n",
    "]\n",
    "\n",
    "for a in candidate_team:\n",
    "    tools = str(a.skills or \"[]\")\n",
    "    print(f\"{a.role:11} | tools={tools:<14} | sees: {a.need_to_know}\")",
))

# 5b. the four forces
cells.append(md(
    "## The four legitimate forces (ranked by how often they actually apply)\n",
    "\n",
    "1. **Context isolation** — *the strongest.* One window holding research notes, style "
    "rules, review criteria, and forty tool results degrades (the lost-in-the-middle problem, "
    "Ch 8). Split roles → each agent gets a small, relevant context.\n",
    "2. **Specialization** — different roles want different prompts, tools, even models (cheap "
    "model for triage, strong model for synthesis). Tune and eval each in isolation.\n",
    "3. **Parallelism** — independent subtasks (research five competitors) fan out and cut "
    "wall-clock time.\n",
    "4. **Privilege separation** — the agent reading untrusted web content must not hold the "
    "DB-write tools. Boundaries between agents are security boundaries.\n",
    "\n",
    "If you can't name one of these for a proposed agent, you don't have a reason to add it.",
))

cells.append(code(
    "# A blunt gate: every agent must claim a named force, or it doesn't get hired.\n",
    "LEGIT_FORCES = {\"context_isolation\", \"specialization\", \"parallelism\", \"privilege_separation\"}\n",
    "\n",
    "def justify(role: str, force: str) -> str:\n",
    "    if force not in LEGIT_FORCES:\n",
    "        return f\"❌ {role}: '{force}' is not a real force — fold this back into one agent.\"\n",
    "    return f\"✅ {role}: justified by {force}.\"\n",
    "\n",
    "print(justify(\"researcher\", \"context_isolation\"))\n",
    "print(justify(\"writer\", \"context_isolation\"))\n",
    "print(justify(\"critic\", \"it_seems_more_capable\"))  # the non-force everyone reaches for",
))

# 5c. predict reliability compounding
cells.append(md(
    "## \U0001F52E Predict: error compounds across handoffs\n",
    "\n",
    "Suppose a pipeline has **three stages in series**, each 90% reliable on its own (it "
    "produces a correct, complete handoff 9 times out of 10).\n",
    "\n",
    "**Predict before you run the next cell:** what is the end-to-end success rate? Is it closer "
    "to 90%, 80%, or 70%?",
))

cells.append(code(
    "# Each stage must succeed for the whole chain to succeed -> probabilities multiply.\n",
    "stage_reliability = 0.90\n",
    "n_stages = 3\n",
    "\n",
    "analytic = stage_reliability ** n_stages\n",
    "print(f\"Analytic end-to-end success: {stage_reliability}^{n_stages} = {analytic:.2f}\")\n",
    "\n",
    "# Monte-Carlo the same chain to *watch* error compound (seeded -> reproducible).\n",
    "TRIALS = 20_000\n",
    "successes = 0\n",
    "for _ in range(TRIALS):\n",
    "    if all(random.random() < stage_reliability for _ in range(n_stages)):\n",
    "        successes += 1\n",
    "empirical = successes / TRIALS\n",
    "print(f\"Empirical over {TRIALS:,} runs:    {empirical:.2f}\")",
))

cells.append(md(
    "**What you just saw.** Three 90%-reliable stages don't give you 90% — they give you "
    "0.9³ = **0.73**. Add a fourth and you're at 0.66. This is why a pipeline of agents can "
    "feel *less* reliable than the single agent it replaced: you multiplied the failure surface. "
    "More agents is more places for a handoff to go wrong.",
))

# 5d. four topologies, mock of each
cells.append(md(
    "## The four working topologies\n",
    "\n",
    "Four named shapes cover nearly everything in production. Below is a tiny **mock** of each "
    "— no LLM calls, just enough structure to feel the shape and its watch-out.\n",
    "\n",
    "| Topology | Fit | Watch out for |\n",
    "|---|---|---|\n",
    "| Supervisor / worker | One coordinator decomposes, delegates, integrates. The production default. | Supervisor becomes bottleneck / single point of failure |\n",
    "| Pipeline | Fixed stages, each transforms the last. Deterministic, per-stage evals. | Errors compound; rigid when the task doesn't fit the stages |\n",
    "| Debate | Agents argue opposing positions; a judge decides. Better calibration. | 2–3× cost for marginal gain on routine tasks |\n",
    "| Blackboard | Agents read/write a shared workspace, react opportunistically. | Hardest to bound/debug; races on shared state |",
))

cells.append(code(
    "# Mock 'agents' are just functions string -> string. The topology is the wiring.\n",
    "def upper(x):    return x.upper()\n",
    "def exclaim(x):  return x + \"!\"\n",
    "def shorten(x):  return x[:24]\n",
    "\n",
    "def supervisor_worker(goal, workers):\n",
    "    # One coordinator routes the goal to a chosen worker and owns the result.\n",
    "    chosen = workers[0]               # a real supervisor would *decide*; we fix it for the demo\n",
    "    return f\"[supervisor] integrated -> {chosen(goal)}\"\n",
    "\n",
    "def pipeline(goal, stages):\n",
    "    x = goal\n",
    "    for stage in stages:              # each stage transforms the previous output\n",
    "        x = stage(x)\n",
    "    return x\n",
    "\n",
    "def debate(claim, judge):\n",
    "    pro, con = f\"PRO: {claim}\", f\"CON: not {claim}\"\n",
    "    return judge(pro, con)            # a judge resolves; costs 2+ agent calls\n",
    "\n",
    "def blackboard(goal, agents, board):\n",
    "    for agent in agents:              # everyone reacts to the shared board, in order here\n",
    "        board.append(agent(goal))     # ...but in reality concurrently -> races\n",
    "    return board\n",
    "\n",
    "print(\"supervisor:\", supervisor_worker(\"summarize q3\", [upper]))\n",
    "print(\"pipeline:  \", pipeline(\"summarize q3\", [upper, exclaim, shorten]))\n",
    "print(\"debate:    \", debate(\"NRR improved\", lambda p, c: f\"judge picks: {p}\"))\n",
    "print(\"blackboard:\", blackboard(\"q3\", [upper, exclaim], board=[]))",
))

cells.append(md(
    "**The headline:** in practice the **supervisor/worker** topology absorbs the others — a "
    "supervisor may run two workers as a debate, or arrange three in a pipeline for one subtask. "
    "Start there. The exotic topologies are seasoning, not the meal.",
))

# 5e. pitfall: lost message + Handoff schema
cells.append(md(
    "## ⚠️ Pitfall: the failure is a *lost message*, not a dumb agent\n",
    "\n",
    "Multi-agent failures are overwhelmingly **interface** failures. The researcher found the "
    "answer, but the free-text summary handed to the writer dropped the key fact; the supervisor "
    "asked for X and the worker solved adjacent-X. Watch a free-text handoff silently lose the "
    "number that the whole brief depended on.",
))

cells.append(code(
    "# A realistic free-text handoff: chatty, human-readable... and lossy.\n",
    "free_text_handoff = (\n",
    "    \"Hey, looked into Q3. Retention is down and mid-market churn is the story. \"\n",
    "    \"The analytics add-on came up a lot in exit surveys. Can you write it up?\"\n",
    ")\n",
    "\n",
    "# The one fact the brief actually needs: NRR fell to 104% from 119%.\n",
    "KEY_FACT = \"NRR 104% (down from 119%)\"\n",
    "print(\"Key fact survived the handoff?\", KEY_FACT in free_text_handoff)  # -> False",
))

cells.append(code(
    "# The fix (Ch 15, Ch 17.3): a *structured* Handoff, validated at the boundary.\n",
    "class Handoff(BaseModel):\n",
    "    task: str                    # what the receiving agent must do\n",
    "    context: str                 # everything needed; assume NO shared memory\n",
    "    artifacts: list[str] = []    # ids/paths of produced outputs\n",
    "    open_questions: list[str] = []  # known unknowns, so they aren't re-derived\n",
    "    done_criteria: str           # how the receiver knows it's finished\n",
    "\n",
    "good = Handoff(\n",
    "    task=\"Write a 1-paragraph brief on the Q3 retention decline.\",\n",
    "    context=\"NRR fell to 104% from 119%, driven by mid-market churn after the \"\n",
    "            \"March pricing change. 61% of churned accounts cited unclear ROI on \"\n",
    "            \"the analytics add-on.\",\n",
    "    artifacts=[\"doc-001\", \"doc-002\"],\n",
    "    open_questions=[\"Is enterprise NRR holding?\"],\n",
    "    done_criteria=\"One paragraph, every claim traceable to a source id.\",\n",
    ")\n",
    "print(\"Key fact survived?\", \"104%\" in good.context and \"119%\" in good.context)  # -> True",
))

cells.append(code(
    "# Validation at the boundary: a bad handoff fails LOUDLY here, not 3 agents later.\n",
    "def validate_handoff(raw: dict) -> Handoff:\n",
    "    try:\n",
    "        return Handoff(**raw)\n",
    "    except ValidationError as e:\n",
    "        # Surface the missing field where it bites, not as a mystery downstream.\n",
    "        missing = [err[\"loc\"][0] for err in e.errors() if err[\"type\"] == \"missing\"]\n",
    "        raise ValueError(f\"Rejected handoff — missing required field(s): {missing}\") from None\n",
    "\n",
    "try:\n",
    "    validate_handoff({\"task\": \"write it up\", \"context\": \"retention stuff\"})  # no done_criteria\n",
    "except ValueError as e:\n",
    "    print(e)",
))

cells.append(md(
    "**What you just saw.** Structure buys three wins at once: nothing important is dropped, "
    "every hop is *validatable* (the bad handoff failed at the boundary, not quietly three agents "
    "later), and your traces become readable documents instead of prompt soup.",
))

# 6. Senior lens --------------------------------------------------------------
cells.append(md(
    "## \U0001F3AF Senior lens\n",
    "\n",
    "The senior move isn't picking the cleverest topology — it's re-asking, at every design "
    "review, **\"would one agent with better tools and context do this more simply?\"** The "
    "default for the whole book holds here: the simplest design that meets the requirements. "
    "You split an agent the way you'd split a monolith — only when a *named* force demands it, "
    "knowing each split multiplies your failure surface and your debugging cost. A four-agent "
    "system that's really a one-agent system with extra latency is the most common (and most "
    "expensive) mistake in this chapter.",
))

# 7. Recap --------------------------------------------------------------------
cells.append(md(
    "## Recap\n",
    "\n",
    "- A multi-agent system **is** a distributed system; add an agent only for a named force.\n",
    "- The forces, ranked: **context isolation** (strongest), specialization, parallelism, "
    "privilege separation.\n",
    "- Reliability **multiplies**: three 90% stages → 0.73. More agents = more failure surface.\n",
    "- **Supervisor/worker** is the default and absorbs the other topologies as sub-patterns.\n",
    "- The dominant failure mode is a **lost message** — fix it with a structured, "
    "boundary-validated `Handoff`, not better in-agent prompts.",
))

# 8. Exercises ----------------------------------------------------------------
cells.append(md(
    "## Exercises\n",
    "\n",
    "Each task *changes* something and asks you to predict the result first.\n",
    "\n",
    "1. **Compounding, harder.** Re-run the reliability cell with `n_stages = 5` and "
    "`stage_reliability = 0.95`. \U0001F52E Predict the end-to-end rate before you run it. Is a "
    "longer chain of *more* reliable stages safe?\n",
    "2. **A third specialist.** Add a `critic` agent to `candidate_team`. Name the force that "
    "justifies it — or argue it should be folded into the writer. Make `justify()` agree.\n",
    "3. **Break a handoff on purpose.** Construct a `Handoff` that *passes* validation but still "
    "loses a fact (a complete-looking `context` that omits the number). What does this tell you "
    "about the limits of schema validation — and what eval (Ch 22) would catch it?\n",
    "4. **Pick a topology.** For “research 5 competitors and write one comparison brief,” "
    "which topology fits, and which force(s) justify the split? Write your answer as a comment.",
))

cells.append(code("# Exercise 1: reliability with n_stages=5, stage_reliability=0.95\n"))
cells.append(code("# Exercise 2: add a 'critic' to candidate_team and justify (or reject) it\n"))
cells.append(code("# Exercise 3: a Handoff that validates but still loses a fact\n"))
cells.append(code("# Exercise 4: choose a topology + name the force(s)\n"))

# 9. Next ---------------------------------------------------------------------
cells.append(md(
    "## Next\n",
    "\n",
    "You decided *whether* and *which*. Next, **build** it: a supervisor that owns the goal and "
    "budget, a researcher wired to RAG, and a writer with no retrieval — each specialist "
    "exposed to the supervisor *as a tool*.\n",
    "\n",
    "- ➡️ Next notebook: [`17-02-supervisor-and-specialists.ipynb`](./17-02-supervisor-and-specialists.ipynb) (the chapter's \U0001F527 Build, §17.5)\n",
    "- \U0001F4D8 Book: §17.1–§17.3\n",
    "- \U0001F527 Blueprint (the production version): [`../../../blueprints/multi-agent-supervisor/`](../../../blueprints/multi-agent-supervisor/)\n",
    "- \U0001F3C1 Capstone: feeds [`../../../capstone/agents/`](../../../capstone/agents/) — checkpoint `ch17-supervisor`.",
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
