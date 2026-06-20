# Part VI — Evaluation, Observability & Quality

> Companion to **Modern Agentic AI Engineer**, Part VI · book chapters 21–23
> Status: 📋 planned (Phase 1)

## Companion emphasis

This is **the discipline that ships agents** — and the book puts it *early on purpose*, before
the deep dives into backends, clouds, and frontends. The reason is structural: a traditional
program is deterministic (tests pass → shipped behavior is tested behavior), but an agentic
system is a *distribution* of behaviors — the same prompt yields different outputs, a "fix"
silently breaks five other cases, a model upgrade shifts behavior overnight. In that world,
intuition and spot-checks are not quality assurance; they are superstition. A team that scales
an *unmeasured* system is scaling its ignorance. So you install measurement first, then scale —
and everything you build in the later parts is designed around these signals, not retrofitted
to them.

The part turns on one image, the **quality flywheel**: *instrument → observe → evaluate →
improve*, spun continuously, each rotation compounding. The companion builds it station by
station:

- **Ch 21 (concept-lab)** makes the mindset physical — an agent is a distribution, "good" is
  layered checkable criteria, and one turn of the flywheel demonstrably moves a number.
- **Ch 22 (walkthroughs, incl. the 🔧 Build)** is the *evaluate* station: golden sets, code
  graders, an LLM-judge done responsibly and *calibrated*, RAG/agent/trajectory + tool-call
  evals, a user-simulator, eval statistics, and a real `evals/` **harness + CI gate** for the
  capstone.
- **Ch 23 (walkthroughs)** is the *instrument* + *observe* stations: tracing agent runs with
  **OpenTelemetry** (spans, GenAI semantic conventions, cost accounting), debugging
  non-deterministic failures from the trace, and run/session dashboards with page-vs-ticket
  alerting.

Two through-lines the whole repo honors carry through here:

- **The eval suite — not the prompt — is the durable asset.** Models and prompts get swapped
  many times; the definition of "good," encoded as tagged data harvested from *your* users'
  real failures, outlives them all and becomes a moat. Every interesting production failure
  becomes a permanent eval case.
- **Instrument once, swap the backend.** OTel is the emission layer; the observability platform
  is a swappable backend. The expensive asset is your instrumentation and the habits built on
  it, not the dashboard rendering it.

Everything here runs **free and offline in `MOCK=1`**: judges, agents, retrievers, simulators,
and the OTel exporter are all mockable/in-memory, so the part that teaches you to measure cost
and quality costs nothing to run.

## Chapters

| Ch | Title | Companion note | Plan |
|---|---|---|---|
| 21 | Quality-First: Why Eval & Observability Come Before Scale | Concept-lab — an agent is a *distribution*, not a function; define "good" as constraints / task-success / quality-gradients, then turn the quality flywheel once (instrument→observe→evaluate→improve) and watch the score move (offline). | [`21-quality-first/PLAN.md`](21-quality-first/PLAN.md) |
| 22 | Evaluation & Quality | Walkthroughs (incl. the 🔧 Build) — golden sets + code graders + a calibrated LLM judge; RAG/agent/trajectory + tool-call-argument evals + a user-simulator + eval statistics; then build the capstone's `evals/` **harness + CI gate** with a safety-gated, slice-aware ratchet. | [`22-evaluation-and-quality/PLAN.md`](22-evaluation-and-quality/PLAN.md) |
| 23 | Observability for Agentic Systems | Walkthroughs — trace an agent run as an **OpenTelemetry** span tree (GenAI conventions) with per-run **cost accounting**; debug a non-reproducible multi-step failure from the trace; aggregate run/session metrics and set page-vs-ticket alerting. | [`23-observability-for-agents/PLAN.md`](23-observability-for-agents/PLAN.md) |

## Run order

Read **in chapter order — the flywheel is sequential**: `21-01-quality-flywheel` installs the
mindset and the vocabulary; Ch 22's `22-01-offline-evals-and-judges` →
`22-02-rag-agent-and-trajectory-evals` → `22-03-eval-harness-and-ci-gate` build the *evaluate*
station (22-03 is the 🔧 **Build**); Ch 23's `23-01-tracing-agent-runs-otel` →
`23-02-debugging-and-dashboards` build *instrument* + *observe*, and 23-02 closes the loop by
feeding a debugged failure back into Ch 22's eval suite. By the end the capstone has both its
**referee** (the eval gate) and its **eyes** (the telemetry).

## Feeds (cross-pillar)

- **Blueprints:** [`blueprints/eval-harness/`](../../blueprints/eval-harness/) (Ch 22),
  [`blueprints/observability-stack/`](../../blueprints/observability-stack/) (Ch 23).
- **Templates:** [`templates/eval-dataset-template/`](../../templates/eval-dataset-template/)
  (the tagged golden-set / JSONL case schema, Ch 22).
- **Capstone:** `capstone/evals/` + `.github/workflows/evals.yml` (Ch 22),
  `capstone/telemetry.py` (Ch 23); checkpoints `ch22-eval-harness`, `ch23-observability`. These
  signals become the SLOs/error budgets formalized in Ch 42 and scale onto Celery in Ch 31.
