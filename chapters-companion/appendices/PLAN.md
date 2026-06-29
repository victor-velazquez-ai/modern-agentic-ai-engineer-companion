# Appendices A–G — Companion Asset Map

> Companion plan · Appendices · book files `chapters/90-appendix-toolchain.typ` …
> `chapters/96-appendix-usecases.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
The appendices are the book's reference layer, and they map onto the companion's *non-notebook*
pillars more than its `learn/` notebooks: a tested setup, the capstone tree, the production
checklist, and — most valuable — the use-case playbook that becomes the `blueprints/` catalog.
This file is the **mapping document**: for each appendix A–G it gives a one-line summary and the
companion asset it becomes, with relative links. It is *not* a per-notebook plan (only E proposes
an optional notebook); the canonical `PLAN.md` notebook template lives in
[`../../docs/CONVENTIONS.md`](../../docs/CONVENTIONS.md).

Most of these assets are owned by other Phase-1 plans (the `blueprints/`, `templates/`, and
`capstone-project/` catalogs). This map is the hand-off: it tells those catalogs which appendix grounds
each asset, and — for G — it enumerates the twelve use cases and a proposed blueprint slug for
each, so the blueprints catalog can cover the full menu.

---

## A — Environment & Toolchain Setup
`chapters/90-appendix-toolchain.typ`

- **What it is:** the one-time toolchain setup (Python 3.12 + `uv`, Node 20+, Docker, AWS CLI,
  API keys & `.env` hygiene, VS Code), ending in a `smoke_test.sh` and a setup checklist.
- **Becomes:** the **living, tested setup** — [`../../docs/SETUP.md`](../../docs/SETUP.md) plus
  [`../../.env.example`](../../.env.example) (already present at the repo root).
  - The book teaches the *book's* full stack (incl. AWS, prod keys); SETUP.md is the *companion's*
    stack and centers the `COMPANION_MOCK=1` zero-key default — the appendix's "minimums, not
    pins" philosophy, made runnable for readers with no cloud account.
  - The appendix's `.env.example` block is the seed; the repo's `.env.example` already extends it
    with `COMPANION_MOCK` and per-chapter grouping. Keep the two in sync (Appendix C lists the
    capstone's required vars — the superset).
  - The appendix smoke test → a `MOCK=1` environment-check that every notebook's setup cell mirrors
    (per [`../../docs/NOTEBOOK-STANDARDS.md`](../../docs/NOTEBOOK-STANDARDS.md) §2).
- **Owner:** `docs/` (this plan only points at it; SETUP.md is authored as a top-level doc).

## B — Cheat Sheets
`chapters/91-appendix-cheatsheets.typ`

- **What it is:** dense daily-driver reference cards — prompting patterns, FastAPI essentials,
  AWS CLI, Docker, Git, Celery — each mapping back to the chapter that explains the *why*.
- **Becomes:** a split between **quick-reference notebooks** (where running beats reading) and
  **`templates/` snippets** (where the value is copy-paste scaffolding). Card-by-card:

  | Cheat sheet (Ch) | Companion asset | Form |
  |---|---|---|
  | Prompting patterns (10, 16) | `learn/.../10-*` walkthroughs already cover these; the table itself → a printable quick-ref notebook `learn/appendices/B-01-prompting-patterns.ipynb` (concept-lab: each pattern as one runnable, mock-able cell) | quick-ref notebook |
  | FastAPI essentials (25) | folds into [`../../templates/fastapi-agent-service/`](../../templates/fastapi-agent-service/) as the minimal `main.py` shape | template |
  | AWS CLI (32–33) | a command quick-ref card in [`../../docs/SETUP.md`](../../docs/SETUP.md) appendix / `learn/part-08-*` README; not a notebook (live AWS isn't mockable cheaply) | doc card |
  | Docker (35) | the canonical Dockerfile/compose lands in a `dockerfile-compose` template (see Ch 35 plan) | template |
  | Git (7) | a markdown quick-ref in `learn/part-02-*/07-*`; reference, no code | doc card |
  | Celery (31) | the config block seeds [`../../capstone-project/`](../../capstone-project/) `workers/celery_app.py` and the Ch 31 walkthrough | capstone + notebook |

  - **Recommendation:** author **one** consolidated quick-reference notebook,
    `B-01-prompting-patterns.ipynb` (the only card whose value is *running* it). Treat the rest as
    text cards living next to their template/capstone home — do **not** force a notebook per card
    (mirrors REPO-PLAN §4's "right asset per chapter, not a forced notebook everywhere").
- **Owner:** mixed — prompting notebook owned here; FastAPI/Docker/Celery cards owned by their
  `templates/` and `capstone-project/` plans.

## C — The Capstone Repository
`chapters/92-appendix-capstone.typ`

- **What it is:** the **canonical directory structure** of the finished `agentic-platform`
  (`app/`, `agents/{raw,graph,pydantic_ai}`, `rag/`, `memory/`, `llm/`, `workers/`, `mcp/`,
  `web/`, `evals/`, `infra/`, `observability/`, …), how to run it (`docker compose up`), the env
  var table, and the part→directory map.
- **Becomes:** [`../../capstone-project/`](../../capstone-project/) — the companion folder that *realizes* this
  exact tree. **Appendix C is the source of truth for the capstone layout**; the capstone's own
  `PLAN.md` and `checkpoints/PLAN.md` build directory-by-directory toward it.
  - The env-var table → reconciled with [`../../.env.example`](../../.env.example) (capstone vars
    are the superset of the companion's).
  - Framing per REPO-PLAN §1: *"build yours from the Build sections; use this to check, compare,
    unblock."* `checkpoints/` match each 🔧 Build section.
- **Owner:** [`../../capstone-project/`](../../capstone-project/) plan (this map only flags C as its blueprint).

## D — Curated Resources
`chapters/93-appendix-resources.typ`

- **What it is:** an opinionated, *non-exhaustive* reading list — foundational papers (in reading
  order), authoritative official docs, durable books, and "staying current" venues.
- **Becomes:** a **curated links reference** in the repo. Lightest-weight option: fold into
  [`../../docs/HOW-TO-USE.md`](../../docs/HOW-TO-USE.md) as a "further reading / where to verify
  what's true this month" section, cross-linked from each part README, rather than a standalone
  `RESOURCES.md` (avoid a thin orphan doc).
  - **2nd-edition note:** per [`../../docs/BOOK-INTEGRATION.md`](../../docs/BOOK-INTEGRATION.md),
    Appendix D gains a new entry — **this companion repo itself** — when the book is republished
    (Phase 3). That edit point is tracked there; this map just records the dependency.
  - Reference-only; **no notebook** (a bibliography teaches nothing by running).
- **Owner:** `docs/` (HOW-TO-USE.md); edit-point tracked in BOOK-INTEGRATION.md.

## E — Glossary
`chapters/94-appendix-glossary.typ`

- **What it is:** ~120 terse, alphabetized working definitions (ABAC → Zero-shot), each tagged
  with the chapter giving the full treatment.
- **Becomes:** primarily a **reference** — the canonical home is the rendered book appendix, with
  notebooks linking terms to it by chapter (`see §N`).
  - **Recommendation — a small, *optional* searchable glossary notebook**
    `learn/appendices/E-01-glossary.ipynb` (worksheet/concept-lab). **Argument for:** it is cheap,
    fully offline, and genuinely useful as a *tool* — load the glossary from a committed
    `data/glossary.csv` (term, definition, chapter) into a tiny pandas frame, expose a one-cell
    `define("MCP")` / substring search, and group by chapter so a reader can pull "every term Ch 13
    introduced." It also becomes the single fixture other notebooks reuse for a "🔮 predict the
    definition" drill. **Argument against:** a static term list doesn't *need* execution, and a
    markdown table renders fine on GitHub. **Verdict: build it, but keep it minimal** — its worth
    is the searchable/filterable affordance and the reusable CSV fixture, not narration. If Phase 2
    is time-boxed, it is the first appendix asset to cut.
- **Owner:** this plan (optional notebook + `data/glossary.csv` fixture).

## F — Production-Readiness Master Checklist
`chapters/95-appendix-master-checklist.typ`

- **What it is:** the consolidated go-live gate, gathered from every 📋 Checklist callout —
  quality/evals, observability, security/safety, reliability, cost, data, operations — framed as
  "an unchecked box is fine *if someone decided it on purpose*."
- **Becomes:** two assets:
  1. A reusable **`templates/` checklist** — `templates/production-readiness-checklist/` (a
     copy-into-your-repo `CHECKLIST.md`, sectioned exactly as the appendix, with space for the
     deliberate-exception notes). Pairs naturally with the ADR/system-design templates.
  2. The **capstone's readiness pass** — [`../../capstone-project/`](../../capstone-project/) carries a filled-in
     instance of this checklist as the Ch 44 "Capstone End-to-End" production-readiness gate
     (REPO-PLAN row 44). The template is the blank; the capstone is the worked example.
- **Owner:** a `templates/` plan (the blank) + the `capstone-project/` plan (the worked pass); this map
  records both targets.

## G — The Agentic Use-Case Playbook
`chapters/96-appendix-usecases.typ`

- **What it is:** the book's capstone-of-the-capstone — a **menu of twelve high-value agentic
  solutions** companies are paying for, each with the same four-part recipe (*Solves · Approach ·
  Build · Pitfalls*), cross-linked to the chapters that taught each part and to Chapter 43's four
  system shapes. Closes with scoping/pitching guidance (pick for value + bounded + reversible +
  measurable; pilot gated on evals; land-and-expand).
- **Becomes:** a **set of `blueprints/`** — one blueprint per use case, framed (per REPO-PLAN §1)
  as *"study and lift"* reference patterns that **recombine the same parts** (retrieval, tools,
  memory, evals, guardrails, backend) the rest of the repo builds. Each blueprint = the recipe
  made runnable: a README mapping back to its Appendix-G section + chapters, a tiny demo, and the
  recombination of existing pattern-blueprints (`agent-loop`, `rag-pipeline`, `eval-harness`, …).
- **Proposed blueprint slugs (the twelve, in the appendix's menu order):**

  | # | Use case (Appendix G) | Core pattern | Proposed blueprint slug |
  |---|---|---|---|
  | 1 | Customer-support agent | RAG + tools + HITL escalation | `customer-support-agent` |
  | 2 | Internal knowledge assistant / employee copilot | Permissioned RAG | `internal-knowledge-assistant` |
  | 3 | Intelligent document processing & extraction | Extraction + schema validation | `document-extraction-pipeline` |
  | 4 | Contract & legal review assistant | Extraction + RAG + HITL redline | `contract-review-assistant` |
  | 5 | Talk-to-your-data analytics copilot | Text-to-SQL over a warehouse | `text-to-sql-analytics` |
  | 6 | Sales & RevOps automation | Tool use + summarization | `sales-revops-automation` |
  | 7 | Ops & incident-response copilot | RAG runbooks + scoped tools + HITL | `incident-response-copilot` |
  | 8 | Research & due-diligence agent | Multi-agent + cited RAG | `research-due-diligence-agent` |
  | 9 | Software-engineering agents | Tool use + multi-agent + CI gates | `software-engineering-agent` |
  | 10 | Content production pipeline | Workflow + brand guardrails | `content-production-pipeline` |
  | 11 | Customer-facing product copilot | In-app RAG + scoped tools | `product-copilot` |
  | 12 | Compliance & monitoring agent | Classification + audit trail + HITL | `compliance-monitoring-agent` |

  - **Recommendation for the blueprints catalog:** group these twelve **"solution" blueprints**
    separately from the **"pattern" blueprints** the chapter plans already feed (`agent-loop`,
    `rag-pipeline`, `memory-module`, `multi-agent-supervisor`, `mcp-server`, `eval-harness`,
    `observability-stack`). Solution blueprints *compose* pattern blueprints — the catalog README
    should show that two-tier dependency so readers see the menu (G) resting on the parts.
- **Owner:** [`../../blueprints/`](../../blueprints/) catalog plan (this map is its input).

---

## Feeds (cross-pillar)
- **Blueprint(s):** the twelve solution blueprints above (from G) → [`../../blueprints/`](../../blueprints/).
- **Template(s):** `production-readiness-checklist` (from F); FastAPI/Docker cards (from B) →
  [`../../templates/`](../../templates/).
- **Capstone:** the whole [`../../capstone-project/`](../../capstone-project/) tree (C is its canonical layout);
  the Ch 44 readiness pass (F).
- **Docs:** [`../../docs/SETUP.md`](../../docs/SETUP.md) + [`../../.env.example`](../../.env.example)
  (A); resources section in [`../../docs/HOW-TO-USE.md`](../../docs/HOW-TO-USE.md) (D).

## Dependencies
- The `blueprints/`, `templates/`, and `capstone-project/` catalog plans consume this map (esp. the G slug
  list and the F/B targets). SETUP.md (A) and the `.env.example` already exist.
- Appendix D's "add the companion repo" edit is a **Phase-3** action, tracked in
  [`../../docs/BOOK-INTEGRATION.md`](../../docs/BOOK-INTEGRATION.md).

## Phase-2 definition of done
- [ ] `SETUP.md` + `.env.example` reflect Appendix A and run a `MOCK=1` smoke check (A).
- [ ] `B-01-prompting-patterns.ipynb` runs offline; other cheat-sheet cards live with their
      template/capstone home (B).
- [ ] `capstone-project/` tree matches Appendix C exactly; `.env.example` covers C's var table (C).
- [ ] Resources list reachable from HOW-TO-USE.md and part READMEs (D).
- [ ] (Optional) `E-01-glossary.ipynb` + `data/glossary.csv` load and search offline (E).
- [ ] `templates/production-readiness-checklist/` exists; capstone carries a filled-in pass (F).
- [ ] All twelve G use cases have a blueprint folder using the slugs above; each README links back
      to its Appendix-G section and composes the relevant pattern blueprints (G).
