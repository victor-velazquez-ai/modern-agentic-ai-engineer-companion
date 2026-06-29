# Ch 15 — Structured Outputs, Validation & Reliability

> Companion plan · Part IV · book file `chapters/15-structured-outputs-and-reliability.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
The moment a model's output is *parsed by a program* instead of read by a human, every quirk
of free-form text becomes a crash. These notebooks build the chapter's four-layer discipline
into running code: write the contract first (a Pydantic schema), make the model honor it
(constrained decoding → validate-and-retry → repair), defend the boundary anyway (semantic
validation + degradation paths), and frame the model as one more unreliable dependency you
already know how to tame. The build is the capstone's single `llm/structured.py` choke
point — after it, *no* capstone code parses raw model text.

## Planned notebooks

### 15-01 · `15-01-schema-first-constrained-decoding.ipynb` — Contract first, then make the model obey
- **Type:** walkthrough
- **Maps to:** book §15.1 (schema-first design — the `TicketTriage` Pydantic model), §15.2
  (guaranteeing valid output — the ladder: prompting → constrained decoding →
  validate-and-retry → repair).
- **Objective:** define an extraction contract as a Pydantic model and get validated,
  typed output back from the model in one call via constrained decoding — then know exactly
  when it still returns "no result."
- **Prereqs:** Ch 4 (typing / Pydantic) · Ch 11 (model APIs, SDK shapes) · Ch 12 (tool
  schemas are the same JSON-Schema lingua franca).
- **Cell arc:**
  - 🧠 mental model: one Pydantic model is your prompt docs, decoding constraint, validator,
    and typed interface at once (Pydantic v2 → JSON Schema).
  - Define the book's `TicketTriage` (StrEnum `Severity`, described fields, `confidence`
    bounded 0–1); inspect its generated JSON Schema.
  - Design *for the model*: flat > nested, enums > free strings (a closed set turns
    hallucination into a catchable validation error), field descriptions are prompt text.
  - 💡 the escape hatch: a `confidence` / nullable / `"unknown"` member lets the model
    express uncertainty *inside* the contract — without one, guessing is mandatory.
  - 🔧 climb the ladder: rung 1 prompting (and why it's notebook-only), then **rung 2
    constrained decoding** — the book's `client.messages.parse(..., output_format=TicketTriage)`
    round trip (Anthropic structured outputs; `claude-opus-4-8`), Pydantic in → validated
    Pydantic out.
  - 🔮 *predict*: feed a vague/empty message — does a guaranteed schema still yield a parsed
    object, or can a refusal / `max_tokens` truncation give "no result"? Run and see.
  - ⚠️ pitfall: the fine print — restricted schema features (no recursion; `ge=0`-style
    bounds validated client-side, not in decoding), so calling code must handle "no object"
    even when the shape is guaranteed.
  - 🎯 senior lens: version the schema with API-contract ceremony — prompts, downstream code,
    and evals all couple to it.
- **Datasets/fixtures:** a handful of sample inbound support messages (tiny, committed in
  `data/`), including one deliberately ambiguous case.
- **APIs & cost:** `MOCK=1` (default) returns a canned valid `TicketTriage` JSON so it runs
  free/deterministic; `MOCK=0` ≈ a few short structured calls. Secrets from env only.
- **You'll be able to:** define a model-friendly schema and get typed, validated output —
  while handling the "guaranteed shape, still no result" case.

### 15-02 · `15-02-validate-retry-repair-degrade.ipynb` — 🔧 Build: the reliability choke point
- **Type:** walkthrough  *(the chapter's 🔧 Build — the capstone `llm/structured.py`)*
- **Maps to:** book §15.2 (validate-and-retry with error feedback; repair as pre-parse
  normalization), §15.3 (semantic validation, guards, graceful degradation), §15.4 (making
  non-deterministic systems dependable), and the §15.4 🔧 Build (`complete_structured`).
- **Objective:** build `complete_structured(prompt, schema)` — constrained decoding first,
  one bounded validate-and-retry pass with the error fed back, repair as normalization,
  metrics on every retry/failure, and a typed `OutputContractError` that routes to a human
  queue.
- **Prereqs:** 15-01; Ch 29 thinking (timeouts/retries/idempotency/circuit breakers) is the
  mental backdrop — surfaced here, built there.
- **Cell arc:**
  - 🧠 mental model: reliability is *layered* — schema constrains the shape, validators the
    meaning, guards the blast radius, degradation the cost of failure, evals the distribution;
    each layer assumes the others sometimes fail.
  - **Validate-and-retry**: the book's `parse_with_retry()` — parse, and on `ValidationError`
    re-prompt with the error attached (Pydantic's message *is* the repair instruction); one
    retry fixes most failures.
  - **Repair**: deterministic pre-parse normalization (strip code fences, trim prose before
    the first `{`, fix trailing commas) *inside* the loop — never a substitute for validation.
  - ⚠️ pitfall: retry loops without budgets are outage amplifiers (a fleet of retries =
    self-inflicted DDoS under provider degradation) — cap attempts (2–3), **count every
    retry** as a metric, decide the spent-budget path in advance.
  - **Semantic validation**: a Pydantic `model_validator` for a cross-field invariant (e.g.
    severity `critical` with `confidence 0.2`, or a `product_area` that doesn't exist) — the
    model is untrusted input inside your trust boundary.
  - **Graceful degradation**: pick a path deliberately — simpler contract, fallback model,
    human queue (`needs_human` exists for exactly this), or honest error — *before* the
    incident, not in the retro.
  - 🔮 *predict*: feed an input that reliably breaks the primary path — which degradation
    branch fires, and what does the user/queue see?
  - Assemble `complete_structured()` (constrained → one retry → repair → metrics →
    `OutputContractError`); 🎯 senior lens: this single observable choke point is what Ch 23
    instruments and Ch 22 evaluates — output contracts make "did the model do well?" a
    computable question.
  - Close by pointing at `capstone-project/llm/structured.py` (every model call in Parts VI–VIII goes
    through it).
- **Datasets/fixtures:** a few canned "bad" model outputs (prose-wrapped JSON, trailing
  comma, a schema-valid-but-semantically-wrong object) to drive repair/validation paths,
  committed in `data/`.
- **APIs & cost:** `MOCK=1` (default) drives the whole loop with canned good/bad responses —
  fully deterministic, free; `MOCK=0` ≈ a few short calls. Secrets from env only.
- **You'll be able to:** build one reliable, observable structured-output entry point with
  bounded retries, repair, semantic guards, and a designed failure path.

## Feeds (cross-pillar)
- **Blueprint(s):** — (no standalone blueprint; the patterns here are consumed by
  `blueprints/agent-loop/` tool-arg validation and the eval harness).
- **Template(s):** — (contributes the Pydantic-contract + `complete_structured` shape reused
  across agent service templates).
- **Capstone:** advances `capstone-project/llm/structured.py` — the platform-wide structured-output
  choke point that `capstone-project/evals/` (Ch 22) and the observability stack (Ch 23) hang off;
  checkpoint `checkpoints/ch15-structured`.

## Dependencies
- Ch 4 (Pydantic / typing) · Ch 11 (model APIs, version pinning, caching) · Ch 12 (tool/JSON
  schemas — same contract machinery; tool-arg authorization is the guard pattern here). Forward
  links: Ch 22 (evals are the statistical safety net these contracts make crisp), Ch 23
  (observability instruments this choke point), Ch 29 (the reliability primitives — timeouts,
  retries, idempotency, circuit breakers — applied to the model as an unreliable dependency).

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` with no errors and no key (canned
  good/bad model responses drive every branch deterministically).
- [ ] `TicketTriage`, `messages.parse(output_format=...)`, `parse_with_retry`, the repair
  step, the `model_validator`, and `complete_structured` match the book's §15 code; examples
  use the latest Claude model as in the book.
- [ ] Retries are capped *and counted as metrics*; a typed `OutputContractError` routes to a
  human-queue stand-in; degradation paths are explicit, not exceptions-only.
- [ ] 15-02 links `capstone-project/llm/structured.py`; each notebook ends with recap + 2–4 exercises;
  secrets from env only; no secrets/PII in committed outputs.
