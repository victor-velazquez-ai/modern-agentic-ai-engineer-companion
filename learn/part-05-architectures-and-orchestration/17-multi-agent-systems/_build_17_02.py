"""Generate 17-02-supervisor-and-specialists.ipynb (walkthrough / the Build).

Builds the §17.5 supervisor + specialists team. MOCK=1 scripts every delegation
and specialist output so it runs free, offline, deterministic. Outputs empty,
execution_count null per NOTEBOOK-STANDARDS. Run, then delete this builder.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "17-02-supervisor-and-specialists.ipynb")


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
    flat = []
    for block in lines:
        flat.extend(block.split("\n"))
    out = []
    for i, line in enumerate(flat):
        out.append(line + "\n" if i < len(flat) - 1 else line)
    return out


cells = []

# 1. Title + header -----------------------------------------------------------
cells.append(md(
    "# \U0001F527 Build a supervisor + specialists team\n",
    "\n",
    "> \U0001F4D3 *Companion to* **Modern Agentic AI Engineer** *· Ch 17 §17.4–§17.5 · type: walkthrough*\n",
    "\n",
    "**The promise:** you'll stand up the chapter's \U0001F527 Build — a supervisor that owns the "
    "goal and budget, a researcher wired to a RAG tool, and a writer with no retrieval — with "
    "each specialist exposed to the supervisor *as a tool*. The capstone's first team.",
))

# 2. Why this matters ---------------------------------------------------------
cells.append(md(
    "## \U0001F9E0 Why this matters\n",
    "\n",
    "The use case: a user asks for a researched brief on a topic covered by the company's "
    "private documents. One agent does this passably — but cramming retrieval noise and writing "
    "guidelines into one context degrades both.\n",
    "\n",
    "So we split it for two named forces: **context isolation** (retrieval noise stays out of "
    "the writing context) and **privilege separation** (only the researcher holds the retrieval "
    "tool). The cleanest way to reach a team in a raw-SDK world is the move you already know: "
    "**each specialist is exposed to the supervisor as a tool.** Delegation becomes a tool call; "
    "the handoff schema becomes the tool's input schema; budgets and logging live in the tool "
    "executor — all machinery from Ch 12 and Ch 16.",
))

# 3. Objectives + prereqs -----------------------------------------------------
cells.append(md(
    "## Objectives & prereqs\n",
    "\n",
    "**By the end you can:**\n",
    "- Implement a `Specialist` whose `as_tool` exposes the handoff schema as its `input_schema`.\n",
    "- Run a `supervise` loop — the Ch 12 tool loop where the *tools are the team*.\n",
    "- See context isolation and a hierarchical `RunBudget` actually working, not just described.\n",
    "\n",
    "**Prereqs:** `17-01` (topologies, the `Handoff` schema); Ch 12 (the tool loop the "
    "supervisor *is*); Ch 16 (`RunBudget`); Ch 13 (the `search_docs` RAG tool); Ch 15 (handoff "
    "schema as tool input).\n",
    "\n",
    "**Cost:** runs free in `MOCK=1` (default) — the mock scripts the supervisor's delegations "
    "and the specialist outputs. `MOCK=0` would cost a few supervisor turns plus one call per "
    "specialist invocation.",
))

# 4. Setup --------------------------------------------------------------------
cells.append(code(
    "# Setup. MOCK=1 (default) -> no key, no network, deterministic.\n",
    "import os\n",
    "import json\n",
    "import random\n",
    "from pathlib import Path\n",
    "\n",
    "from dotenv import load_dotenv\n",
    "\n",
    "load_dotenv()\n",
    "MOCK = os.getenv(\"COMPANION_MOCK\", \"1\") == \"1\"\n",
    "MODEL = \"claude-opus-4-8\"  # the book's default; only used on the MOCK=0 path\n",
    "\n",
    "random.seed(17)  # the mock 'LLM' is scripted, but seed anything stochastic anyway\n",
    "\n",
    "# The live path is opt-in and fails fast with a friendly message if the key is missing.\n",
    "client = None\n",
    "if not MOCK:\n",
    "    if not os.getenv(\"ANTHROPIC_API_KEY\"):\n",
    "        raise SystemExit(\"MOCK=0 needs ANTHROPIC_API_KEY in your environment (.env). \"\n",
    "                         \"Set COMPANION_MOCK=1 to run free and offline.\")\n",
    "    import anthropic\n",
    "    client = anthropic.Anthropic()\n",
    "\n",
    "print(f\"MOCK={MOCK}  model={MODEL}  (MOCK=1 -> free & offline)\")",
))

# 4b. fixtures: the doc base + RAG tool
cells.append(md(
    "### The document base and the RAG tool (Ch 13)\n",
    "\n",
    "The researcher's only skill is `search_docs`, the platform's retrieval tool. We back it "
    "with a tiny committed fixture (`data/docs.json`) and a keyword match — enough to make "
    "*citations* real without a vector DB or any network.",
))

cells.append(code(
    "# Load the tiny doc base committed under data/.\n",
    "DOCS = json.loads((Path(\"data\") / \"docs.json\").read_text(encoding=\"utf-8\"))\n",
    "print(f\"Loaded {len(DOCS)} docs:\", \", \".join(DOCS))\n",
    "\n",
    "# The RAG tool's wire schema, exactly as the supervisor/researcher would see it (Ch 13).\n",
    "SEARCH_DOCS_TOOL = {\n",
    "    \"name\": \"search_docs\",\n",
    "    \"description\": \"Search the company document base. Returns matching docs with their ids.\",\n",
    "    \"input_schema\": {\n",
    "        \"type\": \"object\",\n",
    "        \"properties\": {\"query\": {\"type\": \"string\"}},\n",
    "        \"required\": [\"query\"],\n",
    "    },\n",
    "}\n",
    "\n",
    "def run_rag_tool(name: str, args: dict) -> str:\n",
    "    # Offline keyword retrieval over the fixture. Real version: vector search (Ch 13).\n",
    "    q = args.get(\"query\", \"\").lower()\n",
    "    hits = [d for d in DOCS.values()\n",
    "            if any(w in d[\"text\"].lower() or w in d[\"title\"].lower()\n",
    "                   for w in q.split() if len(w) > 3)]\n",
    "    if not hits:\n",
    "        return \"No matching documents.\"\n",
    "    return \"\\n\".join(f\"[{d['id']}] {d['title']}: {d['text']}\" for d in hits[:3])\n",
    "\n",
    "print(run_rag_tool(\"search_docs\", {\"query\": \"retention churn analytics\"})[:120], \"...\")",
))

# 4c. hierarchical budget
cells.append(md(
    "### The hierarchical budget (Ch 16)\n",
    "\n",
    "`RunBudget` from Ch 16 becomes *hierarchical* here: the **same** budget object is threaded "
    "through the supervisor *and* every specialist, so one runaway worker can't consume the whole "
    "run. We count agent **steps** (each is a model call) rather than tokens to keep the mock "
    "deterministic; the real one charges `resp.usage`.",
))

cells.append(code(
    "class BudgetExceeded(Exception):\n",
    "    pass\n",
    "\n",
    "class RunBudget:\n",
    "    \"\"\"One shared budget for the whole tree (supervisor + specialists).\"\"\"\n",
    "    def __init__(self, max_steps: int):\n",
    "        self.max_steps = max_steps\n",
    "        self.spent = 0\n",
    "        self.ledger = []  # (actor, step) -> a readable per-role trace\n",
    "\n",
    "    def raise_if_spent(self):\n",
    "        if self.spent >= self.max_steps:\n",
    "            raise BudgetExceeded(f\"run budget of {self.max_steps} steps exhausted\")\n",
    "\n",
    "    def charge(self, action_sig: str, steps: int = 1):\n",
    "        self.spent += steps\n",
    "        self.ledger.append((action_sig, self.spent))\n",
    "\n",
    "budget = RunBudget(max_steps=12)\n",
    "print(\"budget ready:\", budget.max_steps, \"steps shared across the whole team\")",
))

# 5. Body ---------------------------------------------------------------------
# 5a. mock LLM
cells.append(md(
    "## The mock 'LLM' (what makes this run free)\n",
    "\n",
    "In `MOCK=1` we replace `client.messages.create(...)` with a scripted responder. It returns "
    "the same *shape* the Anthropic SDK returns — content blocks with `.type`, a `.stop_reason`, "
    "tool-use blocks with `.name`/`.input`/`.id` — so the supervisor and specialist loops below "
    "are the **real** code, not a toy. Swap `MOCK=0` and the identical loops hit the live API.",
))

cells.append(code(
    "# Minimal SDK-shaped response objects so the loops are provider-real.\n",
    "class _Text:\n",
    "    type = \"text\"\n",
    "    def __init__(self, text): self.text = text\n",
    "\n",
    "class _ToolUse:\n",
    "    type = \"tool_use\"\n",
    "    def __init__(self, name, inp, id): self.name, self.input, self.id = name, inp, id\n",
    "\n",
    "class _Resp:\n",
    "    def __init__(self, content, stop_reason): self.content, self.stop_reason = content, stop_reason\n",
    "\n",
    "# A scripted plan: supervisor delegates to researcher, then writer, then integrates.\n",
    "# Keyed by (actor, turn-index) so each role's calls are deterministic.\n",
    "def mock_create(actor, messages, tools):\n",
    "    turn = sum(1 for m in messages if m[\"role\"] == \"assistant\")\n",
    "    if actor == \"supervisor\":\n",
    "        if turn == 0:\n",
    "            return _Resp([_ToolUse(\"researcher\", {\n",
    "                \"task\": \"Find the cause of the Q3 retention decline, with sources.\",\n",
    "                \"context\": \"User wants a brief on why Q3 retention fell. You have search_docs.\",\n",
    "                \"done_criteria\": \"Bullet findings, each with a source id.\"}, \"t1\")], \"tool_use\")\n",
    "        if turn == 1:\n",
    "            return _Resp([_ToolUse(\"writer\", {\n",
    "                \"task\": \"Write a one-paragraph brief on the Q3 retention decline.\",\n",
    "                \"context\": _LAST_RESEARCH[0],  # supervisor passes the FINDINGS, not raw docs\n",
    "                \"done_criteria\": \"One paragraph; keep every [doc-xxx] citation marker.\"}, \"t2\")], \"tool_use\")\n",
    "        return _Resp([_Text(_LAST_DRAFT[0])], \"end_turn\")  # integrate & finish\n",
    "    if actor == \"researcher\":\n",
    "        if turn == 0:\n",
    "            return _Resp([_ToolUse(\"search_docs\",\n",
    "                                   {\"query\": \"retention churn analytics add-on pricing\"}, \"r1\")], \"tool_use\")\n",
    "        findings = (\"- NRR fell to 104% from 119%, driven by mid-market churn [doc-001]\\n\"\n",
    "                    \"- 61% of churned mid-market accounts cited unclear ROI on the analytics add-on [doc-001]\\n\"\n",
    "                    \"- Only 22% of add-on buyers activated >1 dashboard in 90 days; activation predicts renewal [doc-002]\\n\"\n",
    "                    \"- The March change moved the add-on to per-seat pricing, raising prices for small teams [doc-003]\")\n",
    "        _LAST_RESEARCH[0] = findings\n",
    "        return _Resp([_Text(findings)], \"end_turn\")\n",
    "    if actor == \"writer\":\n",
    "        draft = (\"Q3 net revenue retention fell to 104% from 119% [doc-001], driven almost \"\n",
    "                 \"entirely by mid-market churn following the March move to per-seat add-on \"\n",
    "                 \"pricing [doc-003]. Exit surveys point to weak ROI on the analytics add-on \"\n",
    "                 \"(cited by 61% of churned accounts [doc-001]), consistent with telemetry \"\n",
    "                 \"showing only 22% of buyers activated more than one dashboard in 90 days, \"\n",
    "                 \"the strongest predictor of renewal [doc-002].\")\n",
    "        _LAST_DRAFT[0] = draft\n",
    "        return _Resp([_Text(draft)], \"end_turn\")\n",
    "    raise ValueError(actor)\n",
    "\n",
    "_LAST_RESEARCH = [\"\"]  # tiny mailboxes the script uses to thread real outputs forward\n",
    "_LAST_DRAFT = [\"\"]\n",
    "print(\"mock LLM ready\")",
))

# 5b. Specialist class
cells.append(md(
    "## \U0001F527 The `Specialist`: a focused agent the supervisor invokes like a tool\n",
    "\n",
    "A `Specialist` is a focused agent. Its `as_tool` is exactly how the supervisor *sees* it — "
    "a tool whose `input_schema` is the handoff (`task`, `context`, `done_criteria`). Its `run` "
    "is the Ch 12 tool loop, with the shared budget charged on every model call.",
))

cells.append(code(
    "class Specialist:\n",
    "    \"\"\"A focused agent the supervisor can invoke like a tool (book §17.5).\"\"\"\n",
    "    def __init__(self, name, description, system, tools=(), run_tool=None):\n",
    "        self.name, self.system = name, system\n",
    "        self.tools, self.run_tool = list(tools), run_tool\n",
    "        self.as_tool = {                       # how the supervisor sees it\n",
    "            \"name\": name,\n",
    "            \"description\": description,\n",
    "            \"input_schema\": {                  # the Handoff schema, as a tool input\n",
    "                \"type\": \"object\",\n",
    "                \"properties\": {\n",
    "                    \"task\":    {\"type\": \"string\"},\n",
    "                    \"context\": {\"type\": \"string\"},\n",
    "                    \"done_criteria\": {\"type\": \"string\"},\n",
    "                },\n",
    "                \"required\": [\"task\", \"context\", \"done_criteria\"],\n",
    "            },\n",
    "        }\n",
    "\n",
    "    def run(self, handoff: dict, budget) -> str:\n",
    "        # The specialist sees ONLY its handoff — never the supervisor's full context.\n",
    "        prompt = (f\"Task: {handoff['task']}\\n\"\n",
    "                  f\"Context: {handoff['context']}\\n\"\n",
    "                  f\"Done when: {handoff['done_criteria']}\")\n",
    "        messages = [{\"role\": \"user\", \"content\": prompt}]\n",
    "        while True:\n",
    "            budget.raise_if_spent()            # Ch 16: hierarchical budget\n",
    "            if MOCK:\n",
    "                resp = mock_create(self.name, messages, self.tools)\n",
    "            else:\n",
    "                resp = client.messages.create(\n",
    "                    model=MODEL, max_tokens=4096, system=self.system,\n",
    "                    tools=self.tools, messages=messages)\n",
    "            budget.charge(action_sig=self.name)\n",
    "            if resp.stop_reason != \"tool_use\":\n",
    "                return next((b.text for b in resp.content if b.type == \"text\"), \"\")\n",
    "            messages.append({\"role\": \"assistant\", \"content\": resp.content})\n",
    "            messages.append({\"role\": \"user\", \"content\": [\n",
    "                {\"type\": \"tool_result\", \"tool_use_id\": b.id,\n",
    "                 \"content\": self.run_tool(b.name, b.input)}\n",
    "                for b in resp.content if b.type == \"tool_use\"]})\n",
    "\n",
    "print(\"Specialist defined\")",
))

# 5c. the two specialists
cells.append(md(
    "### Two specialists that differ only in job description and access\n",
    "\n",
    "Same class, different *employees*. The `researcher` holds the RAG tool and must cite "
    "source ids; the `writer` has **no retrieval** (privilege separation) and must keep every "
    "citation marker.",
))

cells.append(code(
    "researcher = Specialist(\n",
    "    name=\"researcher\",\n",
    "    description=\"Finds and cites facts from the company document base. \"\n",
    "                \"Delegate all fact-finding here.\",\n",
    "    system=\"You are a research specialist. Use search_docs to gather evidence. \"\n",
    "           \"Return findings as bullet points, each with its source document id. \"\n",
    "           \"Never state a fact without a source.\",\n",
    "    tools=[SEARCH_DOCS_TOOL],          # the RAG tool from Ch 13\n",
    "    run_tool=run_rag_tool,\n",
    ")\n",
    "\n",
    "writer = Specialist(\n",
    "    name=\"writer\",\n",
    "    description=\"Turns research notes into a polished brief. Delegate all drafting \"\n",
    "                \"here; pass the notes in 'context'.\",\n",
    "    system=\"You are a writing specialist. Write a clear, structured brief from the \"\n",
    "           \"notes provided. Keep every citation marker. Do not invent facts beyond the notes.\",\n",
    "    # no tools -> no retrieval. Privilege separation, by construction.\n",
    ")\n",
    "\n",
    "team = [researcher, writer]\n",
    "print(\"writer has retrieval?\", bool(writer.tools), \"| researcher has retrieval?\", bool(researcher.tools))",
))

# 5d. the supervise loop
cells.append(md(
    "## \U0001F527 The `supervise` loop: the Ch 12 tool loop, where the tools are the team\n",
    "\n",
    "The supervisor is *just* a tool loop — but its tools are `[s.as_tool for s in team]`. A "
    "delegation is a tool call; the result integrates straight back into the conversation. The "
    "**same** `budget` is passed down into each `specialist.run(...)`, which is what makes the "
    "budget hierarchical.",
))

cells.append(code(
    "def supervise(goal: str, team, budget) -> str:\n",
    "    by_name = {s.name: s for s in team}\n",
    "    messages = [{\"role\": \"user\", \"content\": goal}]\n",
    "    system = (\"You are the supervisor. Decompose the goal, delegate to your specialists \"\n",
    "              \"via their tools, and integrate results. Give each delegation full context: \"\n",
    "              \"specialists share no memory with you or each other.\")\n",
    "    while True:\n",
    "        budget.raise_if_spent()\n",
    "        if MOCK:\n",
    "            resp = mock_create(\"supervisor\", messages, [s.as_tool for s in team])\n",
    "        else:\n",
    "            resp = client.messages.create(\n",
    "                model=MODEL, max_tokens=4096, system=system,\n",
    "                tools=[s.as_tool for s in team], messages=messages)\n",
    "        budget.charge(action_sig=\"supervisor\")\n",
    "        if resp.stop_reason != \"tool_use\":\n",
    "            return next((b.text for b in resp.content if b.type == \"text\"), \"\")\n",
    "        messages.append({\"role\": \"assistant\", \"content\": resp.content})\n",
    "        # Each delegation calls a teammate's run(), threading the SAME budget down the tree.\n",
    "        messages.append({\"role\": \"user\", \"content\": [\n",
    "            {\"type\": \"tool_result\", \"tool_use_id\": b.id,\n",
    "             \"content\": by_name[b.name].run(b.input, budget)}\n",
    "            for b in resp.content if b.type == \"tool_use\"]})\n",
    "\n",
    "print(\"supervise loop defined\")",
))

# 5e. predict before running the team
cells.append(md(
    "## \U0001F52E Predict: run the team\n",
    "\n",
    "We'll run `supervise(\"Write a brief on why Q3 retention declined...\")`.\n",
    "\n",
    "**Predict before you run the next cell:**\n",
    "1. How many model **steps** will the whole run charge to the shared budget? (Count: "
    "supervisor turns + researcher turns + writer turns.)\n",
    "2. Will the final brief carry `[doc-xxx]` citation markers, even though the *writer* never "
    "touched the retrieval tool?",
))

cells.append(code(
    "goal = (\"Write a one-paragraph, fully-cited brief on why Q3 net revenue \"\n",
    "        \"retention declined, using the company documents.\")\n",
    "\n",
    "budget = RunBudget(max_steps=12)\n",
    "brief = supervise(goal, team, budget)\n",
    "\n",
    "print(\"FINAL BRIEF:\\n\", brief)\n",
    "print(\"\\nSteps charged:\", budget.spent, \"of\", budget.max_steps)\n",
    "print(\"Citations present in writer's output?\", \"[doc-\" in brief)",
))

cells.append(code(
    "# The budget ledger is a readable per-role trace (Ch 23): who spent what, in order.\n",
    "for actor, running_total in budget.ledger:\n",
    "    print(f\"  step {running_total:>2}: {actor}\")",
))

cells.append(md(
    "**What you just saw.** The writer produced citations it could not have retrieved — because "
    "the *supervisor* passed the researcher's findings (with ids) in the handoff `context`. That "
    "is the structured handoff doing its job: the writer needs **no** retrieval tool, only the "
    "notes. Privilege separation and context isolation, both visible in one run.",
))

# 5f. context isolation made visible
cells.append(md(
    "## Context isolation, made visible\n",
    "\n",
    "Each specialist sees **only** its handoff — never the supervisor's full conversation, and "
    "never each other's. Let's print exactly what the writer was handed: research *notes*, not "
    "the raw retrieved documents. Retrieval noise stays out of the writing context.",
))

cells.append(code(
    "# Reconstruct the writer's handoff (turn 1 of the scripted supervisor).\n",
    "writer_handoff = {\n",
    "    \"task\": \"Write a one-paragraph brief on the Q3 retention decline.\",\n",
    "    \"context\": _LAST_RESEARCH[0],   # the FINDINGS the supervisor forwarded\n",
    "    \"done_criteria\": \"One paragraph; keep every [doc-xxx] citation marker.\",\n",
    "}\n",
    "print(\"What the WRITER sees (its entire world):\\n\")\n",
    "print(f\"  task:    {writer_handoff['task']}\")\n",
    "print(f\"  context: {writer_handoff['context'][:90]}...\")\n",
    "print(\"\\nWhat the writer does NOT see: the raw docs, the supervisor's goal text, \"\n",
    "      \"or the researcher's tool calls.\")\n",
    "# Proof it never saw raw retrieval: the full doc text isn't in its context.\n",
    "print(\"Raw doc text leaked into writer context?\",\n",
    "      DOCS[\"doc-001\"][\"text\"] in writer_handoff[\"context\"])  # -> False",
))

# 5g. pitfall: under-specified handoff
cells.append(md(
    "## ⚠️ Pitfall: an under-specified handoff (specialists share no memory)\n",
    "\n",
    "\U0001F52E **Predict:** if the supervisor hands the writer a *thin* context — just \"write up "
    "the retention thing\" — what does the writer produce? Remember: the writer has no retrieval "
    "and no memory of the research. It can only work from the handoff.",
))

cells.append(code(
    "# A deliberately thin handoff: the supervisor under-specifies the context.\n",
    "thin_handoff = {\n",
    "    \"task\": \"Write up the retention thing.\",\n",
    "    \"context\": \"Retention went down in Q3. Mid-market.\",  # the numbers/sources are GONE\n",
    "    \"done_criteria\": \"A paragraph.\",\n",
    "}\n",
    "# The writer can't cite what it was never given -> it solves 'adjacent-X', not X.\n",
    "thin_result = (\"Q3 retention declined, with weakness concentrated in the mid-market \"\n",
    "               \"segment.\")  # vague, uncitable, sources lost\n",
    "print(\"Thin-handoff brief:\\n \", thin_result)\n",
    "print(\"\\nHas citations?\", \"[doc-\" in thin_result, \"| Has the 104%/119% numbers?\",\n",
    "      \"104\" in thin_result)",
))

cells.append(code(
    "# The fix: a RICHER context. Specialists share no memory, so the handoff must carry\n",
    "# everything the receiver needs -- exactly the Handoff discipline from 17-01.\n",
    "rich_handoff = {\n",
    "    \"task\": \"Write a one-paragraph, fully-cited brief on the Q3 retention decline.\",\n",
    "    \"context\": _LAST_RESEARCH[0],   # the full findings, WITH source ids\n",
    "    \"done_criteria\": \"One paragraph; keep every [doc-xxx] citation marker.\",\n",
    "}\n",
    "print(\"Rich context carries the numbers + sources?\",\n",
    "      \"104%\" in rich_handoff[\"context\"] and \"[doc-001]\" in rich_handoff[\"context\"])  # -> True",
))

cells.append(md(
    "**What you just saw.** The worker didn't get dumber — it got *under-briefed*. The most "
    "common multi-agent failure is a lost message at the interface, and the supervisor owns the "
    "interface. Spend your effort on the handoff `context`, not on a cleverer writer prompt.",
))

# 5h. coordination notes + budget propagation
cells.append(md(
    "## Coordination notes (§17.4): why the supervisor topology *is* concurrency control\n",
    "\n",
    "A multi-agent system **is** a distributed system: concurrent workers, shared mutable state, "
    "partial failure. The supervisor topology wins in production largely because it is a "
    "**concurrency-control device** — one component decomposes tasks, assigns owners, and "
    "**serializes conflicting writes** through itself. Contention collapses to the supervisor's "
    "queue discipline (a problem databases solved decades ago) instead of a free-for-all.\n",
    "\n",
    "Two disciplines carry over wholesale:\n",
    "- **Idempotent worker tasks** — a re-dispatched task must be safe to run twice "
    "(at-least-once delivery applies to agents too).\n",
    "- ⚠️ **Propagate budgets down the tree** — the *same* `RunBudget` in supervisor *and* "
    "specialists, so one runaway worker can't starve the team.",
))

cells.append(code(
    "# Prove the budget is genuinely hierarchical: a tiny budget trips mid-delegation,\n",
    "# inside a specialist's loop -- not just at the supervisor's top level.\n",
    "tiny = RunBudget(max_steps=2)  # not enough for supervisor + researcher + writer\n",
    "try:\n",
    "    supervise(goal, team, tiny)\n",
    "except BudgetExceeded as e:\n",
    "    print(\"Stopped early, as designed:\", e)\n",
    "    print(\"Spent before stopping:\", tiny.spent, \"steps  | trace:\", tiny.ledger)",
))

# 6. Senior lens --------------------------------------------------------------
cells.append(md(
    "## \U0001F3AF Senior lens\n",
    "\n",
    "You can't fix a team you can't see. The non-negotiable senior discipline here is "
    "**trace every hop and eval per-role** (Ch 22/23), not just end-to-end — when the brief is "
    "wrong, you need to know *which member* failed: did the researcher miss a source, or did the "
    "writer drop a citation the supervisor handed it? The budget ledger above is the seed of that "
    "per-role trace. And keep re-asking the one-agent question: this team is justified by context "
    "isolation and privilege separation — the moment those forces stop applying, collapse it back. "
    "Sixty lines of orchestration is the right amount; reach for a framework (Ch 18) only when the "
    "machinery you'd hand-roll exceeds it.",
))

# 7. Recap --------------------------------------------------------------------
cells.append(md(
    "## Recap\n",
    "\n",
    "- A `Specialist` is a focused agent; `as_tool` exposes the **handoff schema** as its "
    "`input_schema`, so delegation is just a tool call.\n",
    "- `supervise` is the **Ch 12 tool loop** where the tools are the team; results integrate "
    "straight back.\n",
    "- **Context isolation**: each specialist sees only its handoff — the writer cited sources it "
    "never retrieved, because the supervisor forwarded the notes.\n",
    "- **Privilege separation**: only the researcher holds retrieval; the writer has no tools.\n",
    "- The **same** `RunBudget`, threaded through supervisor and specialists, makes termination "
    "hierarchical — a runaway worker can't consume the run.\n",
    "- The dominant failure is an **under-specified handoff**; the supervisor owns that interface.",
))

# 8. Exercises ----------------------------------------------------------------
cells.append(md(
    "## Exercises\n",
    "\n",
    "1. **Add a critic specialist.** Give the team a `critic` (no retrieval) that the supervisor "
    "calls *after* the writer to check every claim has a citation. Extend the mock script so the "
    "supervisor delegates writer → critic. \U0001F52E Predict how many steps the run now charges.\n",
    "2. **Make a worker task idempotent.** The researcher is re-dispatched (at-least-once "
    "delivery). Add a cache so a repeated identical handoff returns the prior findings without "
    "re-charging a `search_docs` call. Show the budget is lower on the second run.\n",
    "3. **Tighten the budget.** Find the *smallest* `max_steps` that still lets the full "
    "researcher→writer→integrate run finish. What does that number tell you about the team's "
    "minimum cost?\n",
    "4. **Break privilege separation, then restore it.** Temporarily give the `writer` the RAG "
    "tool. What invariant did you just lose, and how would per-role tracing catch a writer that "
    "starts retrieving on its own?",
))

cells.append(code("# Exercise 1: add a 'critic' specialist; extend mock_create for writer -> critic\n"))
cells.append(code("# Exercise 2: idempotent researcher via a handoff cache; show lower budget on re-run\n"))
cells.append(code("# Exercise 3: find the minimum max_steps that still completes the run\n"))
cells.append(code("# Exercise 4: give 'writer' the RAG tool, observe the lost invariant, then revert\n"))

# 9. Next ---------------------------------------------------------------------
cells.append(md(
    "## Next\n",
    "\n",
    "You built the 60-line version. Here's the real one — typed handoffs, hierarchical budgets, "
    "per-role tracing, and a task board with atomic claiming:\n",
    "\n",
    "- \U0001F527 **Blueprint (production version):** [`../../../blueprints/multi-agent-supervisor/`](../../../blueprints/multi-agent-supervisor/)\n",
    "- \U0001F3C1 **Capstone:** this is the seed of [`../../../capstone/agents/`](../../../capstone/agents/) — the supervisor + researcher + writer team. Checkpoint `ch17-supervisor`.\n",
    "- \U0001F4D0 **Template:** the `Specialist`/`Handoff` shapes feed [`../../../templates/agent-project-starter/`](../../../templates/agent-project-starter/).\n",
    "- \U0001F4D8 **Book:** §17.4–§17.5. Next chapter (Ch 18) rebuilds this same team with three frameworks; Ch 20 gates its riskier tools; Part VII runs the supervisor as a Celery job behind FastAPI.",
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
