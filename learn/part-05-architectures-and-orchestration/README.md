# Part V — Agent Architectures & Orchestration

> Companion to **Modern Agentic AI Engineer** · book chapters 16–20
> Status: 📋 Phase 1 — plans only (`PLAN.md` per chapter; notebooks land in Phase 2)

Part IV gave you the raw parts of an agent — the tool loop, RAG, memory, structured outputs.
Part V is where you **wrap strategy and structure around them**: the reasoning patterns that
decide how an agent thinks before it acts, the move from one agent to a coordinated team, the
frameworks that package all of it, the protocol that turns tools into shared infrastructure,
and the human controls that make autonomy *deployable* rather than reckless.

## Emphasis: hands-on walkthroughs, with the guardrails built in

These chapters are **build-heavy**, so the companion is too — mostly **walkthroughs** (build one
mechanism end-to-end in isolation) with a few concept-labs for the judgment-heavy material
(topology choice, framework selection, the autonomy dial). Every chapter has a 🔧 *Build* the
notebooks realize firsthand:

- **Ch 16** — multiple small reasoning-pattern walkthroughs (ReAct, plan-execute, reflection,
  verification), and ⚠️ a dedicated **termination / runaway-cost** notebook: an enforced
  `RunBudget` (step/token/dollar/time caps + repeated-action detection) so no loop here can run
  away. Termination is treated as an *architectural* property, not a prompt.
- **Ch 17** — the 🔧 §17.5 **supervisor + specialists** team (each specialist exposed to the
  supervisor as a tool), with structured handoffs and a hierarchical budget → the
  `multi-agent-supervisor` blueprint and capstone `agents/`.
- **Ch 18** — the 🔧 §18.7 **"same agent, three ways"** build (raw SDK vs LangGraph vs
  Pydantic AI) so framework trade-offs are visible in real code → capstone `agents/graph`,
  `agents/pydantic_ai`.
- **Ch 19** — the 🔧 **build an MCP server** with `FastMCP`, then consume it from the loop and
  draw the security boundaries → the `mcp-server` blueprint and capstone `mcp/`.
- **Ch 20** — the 🔧 **approval gates** build: tier-aware execution that parks a run as
  `waiting_human` and resumes it with the human decision injected as a tool result.

Two threads run across the whole Part, by design: **bounded autonomy** (every loop is externally
capped — Ch 16's `RunBudget` becomes hierarchical in Ch 17 and tier-gated in Ch 20) and
**structured boundaries** (typed handoffs, MCP schemas, risk tiers — the portable artifacts that
outlast any framework). All notebooks run free and deterministically in `MOCK=1`; live API paths
are documented and opt-in.

## Chapters in this part

| Ch | Title | Companion emphasis | 🔧 Build | Plan |
|----|-------|--------------------|---------|------|
| 16 | Agent Reasoning Patterns | Walkthroughs: ReAct + interleaved thinking; plan-execute / reflect / verify; ⚠️ `RunBudget` & termination guards | Reasoning patterns + enforced budget | [PLAN](16-agent-reasoning-patterns/PLAN.md) |
| 17 | Multi-Agent Systems | Concept-lab on topology choice + the supervisor/specialists walkthrough (structured handoffs, hierarchical budget) | §17.5 supervisor + specialists → `blueprints/multi-agent-supervisor`, capstone `agents/` | [PLAN](17-multi-agent-systems/PLAN.md) |
| 18 | The Framework Landscape | "Same agent, three ways" walkthrough + a framework-selection concept-lab (forces → matrix → ADR) | §18.7 raw vs LangGraph vs Pydantic AI → capstone `agents/graph`, `agents/pydantic_ai` | [PLAN](18-framework-landscape/PLAN.md) |
| 19 | Model Context Protocol (MCP) & Tool Ecosystems | Build an MCP server (`FastMCP`), then consume it + draw the three security boundaries | Build an MCP server → `blueprints/mcp-server`, capstone `mcp/` | [PLAN](19-mcp-and-tool-ecosystems/PLAN.md) |
| 20 | Human-in-the-Loop & Agent UX | Concept-lab on the autonomy dial (risk tiers + confidence escalation) + the approval-gates walkthrough | §20.6 approval gates (park `waiting_human` → resume) → capstone `approvals` | [PLAN](20-human-in-the-loop/PLAN.md) |

## Conventions

Plans follow the canonical template in [`docs/CONVENTIONS.md`](../../docs/CONVENTIONS.md);
notebooks (Phase 2) follow [`docs/NOTEBOOK-STANDARDS.md`](../../docs/NOTEBOOK-STANDARDS.md). The
master chapter→asset map lives in [`docs/REPO-PLAN.md`](../../docs/REPO-PLAN.md) §4. Notebooks
are named `NN-MM-short-title.ipynb` and link back to the book by section number (e.g. "see §17.5").
