# Ch 05 — Clean Code & Design that Lasts

> Companion plan · Part II · book file `chapters/05-clean-code-and-design.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This chapter is craft, so its companion is a **refactoring drill** plus a **pattern
concept-lab** — the reader takes a messy function and the book's five patterns from *prose* to
*running code* they can change. It also stands up the seams (the `LLMProvider` protocol +
adapter + factory, domain objects that own their rules) that make every later chapter testable
and swappable — the skeleton Part VII grows into a real backend.

## Planned notebooks

### 05-01 · `05-01-refactor-for-cognitive-load.ipynb` — Make a function fit in your head
- **Type:** drill
- **Maps to:** book §5.1 (naming, functions, cognitive load), §5.5 (refactoring safely; the
  smells of AI codebases)
- **Objective:** refactor a three-jobs-interleaved function into one-job-per-level helpers
  *without changing behavior*, guarded by a characterization test.
- **Prereqs:** Ch 4 (typing, structure).
- **Cell arc:**
  - 🧠 cognitive load as a *budget*: working memory holds ~6 things; every vague name / extra
    nesting level / two-job function spends from it.
  - Start from the book's `handle(self, msg)` (fetch + build prompt + call + persist, all
    interleaved); write a tiny characterization test pinning current output first.
  - 🔮 *predict* which refactor lowers load most; extract `recent`/`build_prompt`/`append`
    seams one step at a time, re-running the test after each.
  - Naming drill: rename `n`/`data2`/`process` to intent-revealing names; guard clauses to
    flatten nesting; collapse a 4-arg call into a dataclass.
  - ⚠️ pitfall: refactoring code that has *no* test — write the characterization test first,
    or you're editing blind.
  - Spot-the-smell gallery on AI-generated code: prompt spaghetti, the dict-of-everything,
    notebook residue, `except Exception: return None` wallpaper, duplicated retry helpers.
  - 🎯 senior lens: structure is the highest-leverage instruction you give an AI assistant —
    it imitates the surrounding code, so clean domains beget clean generations.
- **Datasets/fixtures:** the before/after snippet inline; a 3-line fake `db`/`llm` so the
  function runs offline.
- **APIs & cost:** none / offline.
- **You'll be able to:** refactor safely in small, test-covered steps and name the recognizable
  smell profile of AI-written code on sight.

### 05-02 · `05-02-patterns-as-seams.ipynb` — The five patterns you'll actually use
- **Type:** concept-lab
- **Maps to:** book §5.2 (SOLID without dogma), §5.3 (the patterns you'll actually use), §5.4
  (domain modeling / where business logic lives) — the chapter's 🔧 Build (`providers/` +
  `domain/`)
- **Objective:** wire the same provider layer the book builds — Protocol seam, Adapter,
  Factory, DI, Strategy, Repository — and put a domain rule where the data that owns it lives.
- **Prereqs:** 05-01; Ch 4 Protocols.
- **Cell arc:**
  - 🧠 the one idea under all five patterns: each creates a *seam* — a typed boundary one side
    can change/fake/swap without the other knowing.
  - 🔧 define the `LLMProvider` Protocol; write a `FakeProvider` adapter (offline) and a
    `make_provider(settings)` factory driven by config (`match` on vendor).
  - Inject the provider into an `Agent` via its constructor (DI is just a constructor arg, no
    framework); 🔮 *predict* what swapping the factory's branch changes downstream.
  - Strategy as a Protocol *or* a plain function (retrieval: keyword vs vector vs hybrid);
    Repository as a domain-term interface hiding persistence.
  - SOLID as change-heuristics, not commandments: run the "count the files a plausible change
    touches" test on the seamed design vs a tangled one.
  - 🔧 domain modeling: a `Thread.append` that enforces its own `token_budget` (raises
    `BudgetExceeded`) — the rule lives *with* the data, true everywhere.
  - ⚠️ pitfall: the anemic domain model — rules smeared across handlers/services drift out of
    sync; and over-abstraction (interfaces with one impl forever) fails the same load budget.
  - 📋 the clean-code & design checklist as a self-audit.
  - 🎯 senior lens: abstraction is a *loan* repaid only by a real second impl, test seam, or
    isolation need — knowing when to take it is the senior skill.
- **Datasets/fixtures:** none — a `FakeProvider` returning canned text keeps it fully offline.
- **APIs & cost:** mockable by design (`FakeProvider`); no live model call needed to learn the
  patterns. A real Anthropic adapter is shown but only exercised live if a key is present.
- **You'll be able to:** build the provider/domain skeleton (seams + rules-in-the-domain) that
  the capstone and every later part are fleshed out from.

## Feeds (cross-pillar)
- **Blueprint(s):** — (the Protocol→Adapter→Factory→DI shape recurs in `blueprints/agent-loop/`
  and the provider layer, but is authored there, not here).
- **Template(s):** — (the seam/domain conventions inform `templates/agent-project-starter/`,
  Ch 12; nothing authored here).
- **Capstone:** seeds `capstone/.../providers/` (Protocol + adapter + factory) and
  `capstone/.../domain/` (`Thread`/`Message`/`Run` owning their rules) — the chapter's 🔧 Build.

## Dependencies
- Ch 4 (typing, Protocols, `core/Settings`). The `FakeProvider` seam here is what makes Ch 7's
  `FakeLLM` testing possible — testability is a design property earned at construction time.

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` (offline via `FakeProvider`) with no errors.
- [ ] Provider/factory/DI and the `Thread.append` budget rule match the book's §5 code exactly.
- [ ] The refactor keeps behavior (characterization test stays green); AI-smell gallery present.
- [ ] Recap + 2–4 exercises per notebook; links resolve to the capstone `providers/`+`domain/`.
