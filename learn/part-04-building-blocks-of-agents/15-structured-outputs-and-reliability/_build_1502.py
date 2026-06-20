"""Generator for notebook 15-02. Run once, then delete."""
import json

def md(text):
    lines = text.split("\n")
    src = [l + "\n" for l in lines[:-1]] + ([lines[-1]] if lines[-1] != "" else [])
    return {"cell_type": "markdown", "metadata": {}, "source": src}

def code(text):
    lines = text.split("\n")
    src = [l + "\n" for l in lines[:-1]] + ([lines[-1]] if lines[-1] != "" else [])
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": src}

cells = []

cells.append(md(
"""# Build: the reliability choke point — `complete_structured()`

> \U0001F4D3 *Companion to* **Modern Agentic AI Engineer** *· Ch 15 §15.2–§15.4 · type: walkthrough (🔧 Build)*

**The promise:** build one reliable, observable entry point for structured model output —
constrained decoding first, **one** bounded validate-and-retry pass with the error fed back,
repair as pre-parse normalization, a metric on every retry and failure, semantic guards, and
a typed `OutputContractError` that routes to a human queue. This is the capstone's
`llm/structured.py` choke point: after it, *no* capstone code parses raw model text.

Notebook **15-02**. Runs **free and offline** by default (`COMPANION_MOCK=1`) — canned good
*and* bad responses drive every branch deterministically."""))

cells.append(md(
"""## \U0001F9E0 Why this matters

15-01 gave you a typed object from a clean call. Production is not a clean call. The model is
*one more unreliable dependency* — given the same input it may return brilliance, malformed
JSON, or a confidently-shaped wrong answer — and you already know how to build reliable
systems out of unreliable parts.

So reliability here is **layered**, and each layer catches what the one above lets through:

- the **schema** constrains the *shape* (15-01),
- **validators** constrain the *meaning*,
- **guards** constrain the *blast radius*,
- **degradation paths** bound the *cost of failure*,
- **evals** (Ch 22) watch the *distribution* over time.

No single layer suffices. The system is dependable when every layer assumes the others will
sometimes fail. This notebook builds the first four into one function."""))

cells.append(md(
"""## Objectives & prereqs

**By the end you can:**
- run a bounded **validate-and-retry** loop that feeds the validation error back as the repair
  instruction;
- apply **repair** (deterministic normalization) as a pre-parse step — never a substitute for
  validation;
- add a **semantic** `model_validator` for a cross-field invariant the schema can't express;
- choose a **degradation path** deliberately and route failures to a human queue via a typed
  `OutputContractError`; and
- assemble all of it into `complete_structured()` with **counted** retries.

**Prereqs:** notebook **15-01** (the `TicketTriage` contract). Ch 29 (timeouts / retries /
idempotency / circuit breakers) is the mental backdrop — surfaced here, built there. Run
**Setup** first."""))

cells.append(code(
'''import json
import os
import random
import re
from collections import Counter
from enum import StrEnum
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, model_validator

load_dotenv()

# MOCK=1 (default): canned good/bad responses drive every branch, free & offline.
# MOCK=0: hit the live Anthropic API (needs ANTHROPIC_API_KEY; ~a few short calls).
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(15)  # deterministic where we have a choice

DATA = Path("data")

print(f"MOCK mode: {MOCK}  (set COMPANION_MOCK=0 in .env to hit the live API)")
if not MOCK and not os.getenv("ANTHROPIC_API_KEY"):
    raise RuntimeError(
        "MOCK=0 but ANTHROPIC_API_KEY is not set. "
        "Add it to .env, or set COMPANION_MOCK=1 to run free and offline."
    )'''))

cells.append(md(
"""## The contract (from 15-01), now with a semantic guard

We reuse `TicketTriage` from 15-01 and add what the schema *cannot* express: cross-field and
referential rules. A `model_validator(mode="after")` runs once the shape is valid and rejects
objects that are *syntactically perfect but semantically wrong*:

- a `product_area` we've never shipped (referential check against real data), and
- `severity="critical"` paired with a low `confidence` (a cross-field invariant — a
  low-confidence "critical" must escalate, not auto-resolve).

The stance: **the model is untrusted input inside your trust boundary.** Its output earns the
same scrutiny as a request body off the public internet."""))

cells.append(code(
'''# The product areas we actually ship. A referential check turns a plausible-sounding
# hallucination ("teleportation") into a catchable error.
KNOWN_PRODUCT_AREAS = {"billing", "api", "dashboard", "reports", "auth", "mobile"}


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketTriage(BaseModel):
    """Structured triage of an inbound support message (with semantic guards)."""

    summary: str = Field(description="One sentence, plain language.")
    severity: Severity
    product_area: str = Field(
        description="Affected area, e.g. 'billing', 'api', 'dashboard'."
    )
    needs_human: bool = Field(
        description="True if an agent cannot safely resolve this alone."
    )
    confidence: float = Field(
        ge=0, le=1, description="Self-assessed confidence in this triage."
    )

    @model_validator(mode="after")
    def _semantic_checks(self):
        # Referential: the area must be one we actually ship.
        if self.product_area not in KNOWN_PRODUCT_AREAS:
            raise ValueError(
                f"product_area {self.product_area!r} is not a known area "
                f"{sorted(KNOWN_PRODUCT_AREAS)}"
            )
        # Cross-field invariant: a low-confidence 'critical' must escalate, not auto-resolve.
        if self.severity == Severity.CRITICAL and self.confidence < 0.5:
            raise ValueError(
                "severity 'critical' requires confidence >= 0.5; "
                "a low-confidence critical must be escalated to a human"
            )
        return self


TicketTriage'''))

cells.append(md(
"""## A typed failure + a metrics sink

Two small pieces the whole choke point hangs on:

- **`OutputContractError`** — a *typed* exception (not a bare `ValueError`) so calling code can
  catch exactly this and route it. It carries the schema name, the last error, and the attempt
  count for the human queue.
- **`METRICS`** — a stand-in for your real telemetry (Ch 23). The point the chapter hammers:
  **count every retry and every failure.** A rising retry rate is an early-warning signal; an
  uncounted retry is an invisible outage amplifier."""))

cells.append(code(
'''class OutputContractError(Exception):
    """Raised when a schema-conformant object could not be produced within budget."""

    def __init__(self, schema_name: str, last_error: str | None, attempts: int):
        super().__init__(
            f"{schema_name} could not be produced after {attempts} attempt(s): {last_error}"
        )
        self.schema_name = schema_name
        self.last_error = last_error
        self.attempts = attempts


# Stand-in for real telemetry (Ch 23 instruments this exact choke point).
METRICS: Counter = Counter()


def reset_metrics() -> None:
    METRICS.clear()


print("Typed error + metrics sink ready.")'''))

cells.append(md(
"""## Layer 1 · Repair — deterministic normalization

The cheapest fix for the most common failures: the model wrapped JSON in a ```` ```json ````
fence, prepended "Sure! Here's your JSON:", or left a trailing comma. `repair()` is pure,
instant, and deterministic — it strips fences and prose, slices to the outermost `{...}`, and
removes trailing commas.

⚠️ It runs **inside** the parse step as *pre-parse normalization* — it is **never** a
substitute for validation. Repair can silently change meaning; only the validator decides
whether the result is acceptable."""))

cells.append(code(
r'''def repair(raw: str) -> str:
    """Best-effort normalization of almost-JSON. Pre-parse only; validation still decides."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)   # opening code fence
    text = re.sub(r"\s*```$", "", text)            # closing code fence
    start = text.find("{")                          # trim prose before the object
    if start > 0:
        text = text[start:]
    end = text.rfind("}")                           # trim prose after the object
    if end != -1:
        text = text[: end + 1]
    text = re.sub(r",(\s*[}\]])", r"\1", text)      # drop trailing commas
    return text.strip()


bad = json.loads((DATA / "bad_outputs.json").read_text(encoding="utf-8"))

print("--- prose-wrapped, before ---")
print(bad["prose_wrapped"][:60], "...")
print("\n--- after repair() ---")
print(repair(bad["prose_wrapped"]))'''))

cells.append(md(
"""## \U0001F52E Predict, then run — does repair alone make it valid?

Two of our canned bad outputs are *syntax* problems (`prose_wrapped`, `trailing_comma`); one
is a *missing field* (`missing_field`); one is *semantically wrong* (`semantically_wrong`,
`product_area="teleportation"`).

**Question:** after `repair()` + `model_validate_json()`, which of the four become a valid
`TicketTriage`, and which still fail — and *why* does each failure fail (syntax vs. schema
vs. semantics)?

Predict, then run."""))

cells.append(code(
r'''for key in ["prose_wrapped", "trailing_comma", "missing_field", "semantically_wrong"]:
    try:
        obj = TicketTriage.model_validate_json(repair(bad[key]))
        print(f"{key:>18}:  OK  -> {obj.severity.value}/{obj.product_area}")
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(p) for p in first["loc"]) or "<model>"
        print(f"{key:>18}:  FAIL at {loc}: {first['msg'][:70]}")'''))

cells.append(md(
"""**What you just saw.** Repair fixes *syntax* — the prose-wrapped and trailing-comma cases
parse cleanly. It does **nothing** for a missing field (a *schema* failure) or for
`teleportation` (a *semantic* failure caught by our `model_validator`). Different layers, different
jobs. That's why the next layer exists."""))

cells.append(md(
"""## Layer 2 · Validate-and-retry, with the error fed back

When repair + validation still fails, re-prompt — and attach the error, because **Pydantic's
message *is* the repair instruction**. One retry fixes the overwhelming majority of failures.

This is the book's `parse_with_retry()` shape, with two production-grade additions the
chapter insists on:

- **a hard attempt cap** (2–3), and
- **a metric on every attempt, every retry, every failure.**"""))

cells.append(code(
r'''def parse_with_retry(call, schema, attempts: int = 3):
    """Parse the model output; on ValidationError, re-prompt with the error attached.

    `call(error_hint=...)` returns raw model text. Repair runs as pre-parse normalization.
    Every attempt/retry/failure is counted — uncounted retries are invisible outages.
    """
    last_error = None
    for i in range(attempts):
        METRICS["attempts"] += 1
        if i > 0:
            METRICS["retries"] += 1          # count EVERY retry (early-warning signal)
        raw = call(error_hint=last_error)    # feed the prior error back as the fix instruction
        try:
            return schema.model_validate_json(repair(raw))
        except ValidationError as exc:
            last_error = str(exc)            # becomes the next attempt's hint
    METRICS["failures"] += 1
    raise OutputContractError(schema.__name__, last_error, attempts)


print("parse_with_retry ready.")'''))

cells.append(md(
"""Now a mock model whose **first** attempt drops a field and whose **second** (having "seen"
the error) returns a valid object. In `MOCK=0` the same `call` signature hits the live API and
includes `error_hint` in the re-prompt."""))

cells.append(code(
r'''def make_retry_mock(responses: list[str]):
    """A deterministic stand-in for the model: returns each canned response in order.

    In MOCK=0 you'd instead call the API here and weave `error_hint` into the prompt:
        prompt = base if error_hint is None else f"{base}\n\nYour last output was invalid:\n{error_hint}"
    """
    state = {"i": 0}

    def call(error_hint=None):
        i = state["i"]
        state["i"] = min(i + 1, len(responses) - 1)
        return responses[i]

    return call


reset_metrics()
# First response is missing a field; the second (post-feedback) is valid.
flaky = make_retry_mock([bad["missing_field"], bad["valid_after_retry"]])
triage = parse_with_retry(flaky, TicketTriage, attempts=3)

print("Recovered after feedback:", triage.severity.value, "/", triage.product_area)
print("metrics:", dict(METRICS))   # note: 2 attempts, 1 retry, 0 failures'''))

cells.append(md(
"""## ⚠️ Pitfall — retry loops without budgets are outage amplifiers

Every retry doubles cost and latency. Under provider degradation, a fleet of well-meaning
retry loops becomes a **self-inflicted DDoS**: each client hammers a struggling provider,
deepening the very outage it's reacting to.

The discipline is three rules, all of which `parse_with_retry` already follows:

1. **Cap attempts** (2–3) — `attempts` is bounded, never a `while True`.
2. **Count every retry** as a metric — a rising `retries` rate is your early warning.
3. **Decide the spent-budget path *in advance*** — that's the next section.

Watch the budget *deny* a forever-broken input instead of looping into the void:"""))

cells.append(code(
r'''reset_metrics()
always_bad = make_retry_mock([bad["semantically_wrong"]])  # never satisfies the validator

try:
    parse_with_retry(always_bad, TicketTriage, attempts=2)  # capped at 2
except OutputContractError as exc:
    print("Budget spent, loop stopped (did NOT hammer forever).")
    print("attempts used:", exc.attempts, "| metrics:", dict(METRICS))'''))

cells.append(md(
"""## Layer 3 · Graceful degradation — decide "and then what?" up front

Budget exhausted, validation still red — the system must **degrade, not die**. Pick the
failure mode *per use case, deliberately, in the design review* (not the incident retro):

- **Simpler contract** — if rich triage fails, a bare severity classification may still
  succeed. Partial structure beats none.
- **Fallback model** — a different family often un-sticks an input that reliably breaks the
  primary. (A routing decision, not a loyalty one.)
- **Human queue** — queue the raw text, attempts, and errors. `needs_human` exists in the
  schema for exactly this; for high-stakes writes it's the *design*, not a failure.
- **Honest error** — "I couldn't process this reliably" with a retry affordance preserves
  trust; a confidently wrong answer spends it.

Here the deliberate choice is the **human queue**, reached via the typed `OutputContractError`."""))

cells.append(code(
r'''HUMAN_QUEUE: list[dict] = []  # stand-in for a real review queue / ticket system


def route_to_human(raw_text: str, err: OutputContractError) -> dict:
    """The designed failure path: hand the item to a human with full context."""
    METRICS["degraded_to_human"] += 1
    item = {
        "raw_text": raw_text,
        "schema": err.schema_name,
        "attempts": err.attempts,
        "last_error": err.last_error,
        "status": "needs_human",
    }
    HUMAN_QUEUE.append(item)
    return item


print("Degradation path wired: failures route to a human queue.")'''))

cells.append(md(
"""## \U0001F52E Predict, then run — which branch fires on a forever-broken input?

We'll feed `complete_structured()` (assembled next) an input the primary path can never
satisfy (`semantically_wrong`).

**Question:** after the capped retries are spent, which degradation branch fires — exception
to the caller, or a human-queue hand-off? And what does the queue *see*? Predict, then run the
assembled function below."""))

cells.append(md(
"""## \U0001F527 Assemble — `complete_structured()`

One observable choke point, in the book's order: **constrained decoding first → one
validate-and-retry pass (with repair inside) → metrics on everything → on spent budget, the
*designed* degradation path** (human queue) rather than an unhandled exception.

In `MOCK=0`, `_constrained_call` is `client.messages.parse(..., output_format=schema)` from
15-01; the retry `call` re-prompts with `error_hint`. In `MOCK=1`, both are driven by the
canned responses so every branch is deterministic and free."""))

cells.append(code(
r'''def complete_structured(
    prompt: str,
    schema,
    *,
    mock_responses: list[str] | None = None,
    attempts: int = 3,
    degrade=route_to_human,
):
    """The platform-wide structured-output entry point.

    constrained decoding -> one validate-and-retry pass (repair inside) -> metrics ->
    designed degradation. Returns a validated `schema` instance OR the degradation result.
    """
    METRICS["calls"] += 1

    if MOCK:
        # Deterministic stand-in: the canned responses ARE the model's (mis)behavior.
        responses = mock_responses if mock_responses is not None else ["{}"]
        call = make_retry_mock(responses)
    else:
        # --- live path ---
        import anthropic

        client = anthropic.Anthropic()

        def call(error_hint=None):
            content = prompt if error_hint is None else (
                f"{prompt}\n\nYour previous output was invalid. "
                f"Fix exactly this and return only the corrected JSON:\n{error_hint}"
            )
            resp = client.messages.parse(
                model="claude-opus-4-8",
                max_tokens=1024,
                messages=[{"role": "user", "content": content}],
                output_format=schema,
            )
            parsed = getattr(resp, "parsed_output", None)
            # Normalize to raw JSON text so the retry loop owns validation in one place.
            return parsed.model_dump_json() if parsed is not None else "{}"

    try:
        return parse_with_retry(call, schema, attempts=attempts)
    except OutputContractError as exc:
        # Designed degradation — NOT an unhandled exception.
        return degrade(prompt, exc)


print("complete_structured() assembled.")'''))

cells.append(md(
"""### Run it both ways — the happy path and the designed-failure path"""))

cells.append(code(
r'''reset_metrics()
HUMAN_QUEUE.clear()

# 1) Happy path: first response bad, retry succeeds -> a validated object.
good = complete_structured(
    "Triage this support message: CSV export columns are out of order.",
    TicketTriage,
    mock_responses=[bad["missing_field"], bad["valid_after_retry"]],
    attempts=3,
)
print("HAPPY  ->", type(good).__name__, "|", good.severity.value, "/", good.product_area)

# 2) Designed-failure path: forever-broken input -> human queue (the predicted branch).
result = complete_structured(
    "Triage this support message: <input that reliably breaks the primary path>",
    TicketTriage,
    mock_responses=[bad["semantically_wrong"]],
    attempts=2,
)
print("DEGRADE->", result["status"], "| attempts:", result["attempts"])
print("human queue depth:", len(HUMAN_QUEUE))
print("metrics:", dict(METRICS))'''))

cells.append(md(
"""**What you just saw.** The forever-broken input did **not** raise into your request handler
and did **not** loop forever — it spent its capped budget, got counted, and landed in the
human queue with full context (`attempts`, `last_error`, the raw text). That branch was
*chosen*, not stumbled into. The happy path, meanwhile, self-healed on the single retry the
budget allows. Every path is observable in `METRICS`."""))

cells.append(md(
"""## \U0001F3AF Senior lens — one choke point makes quality computable

`complete_structured()` is deliberately the *single* place model text becomes typed data.
That single, observable seam is what pays off across the rest of the book:

- **Ch 23 (observability)** instruments exactly this function — retry rate, failure rate, and
  degradation counts are platform SLOs, not per-call afterthoughts.
- **Ch 22 (evals)** hangs off the *output contract*: a well-defined schema turns the fuzzy
  question "did the model do well?" into a **computable** one, measured over a distribution.

The junior sprinkles `json.loads` and bare `try/except` across the codebase; the senior funnels
every model call through one instrumented contract — because the difference between a 0.5%
failure rate nobody notices and one that fills the support queue is entirely in what the system
does *next*. Error handling isn't the appendix of an LLM design; it **is** the design."""))

cells.append(md(
"""## Recap

- **Reliability is layered:** schema (shape) → validators (meaning) → guards (blast radius) →
  degradation (cost of failure) → evals (distribution). Each assumes the others sometimes fail.
- **Validate-and-retry** feeds the validation error back as the repair instruction; one retry
  fixes most failures. **Repair** fixes *syntax* only and runs *inside* parse — never instead
  of validation.
- **Budgets are non-negotiable:** cap attempts (2–3), **count every retry and failure**, and
  decide the spent-budget path in advance — uncapped retries are outage amplifiers.
- **Semantic validators** reject schema-valid-but-wrong objects (`teleportation`, low-confidence
  "critical") — the model is untrusted input inside your trust boundary.
- **Degrade deliberately:** a typed `OutputContractError` routes to a designed path (human
  queue here), not an unhandled exception. `complete_structured()` is the one observable choke
  point Ch 22 evaluates and Ch 23 instruments."""))

cells.append(md(
"""## Exercises

Predict first, then run. Solutions land in `solutions/` (Phase 2).

1. **Add a degradation tier.** Before the human queue, try a **simpler contract** (e.g. a
   `severity`-only model). Wire it into `complete_structured` as the first fallback and predict
   which inputs it rescues that the full schema couldn't.
2. **Make retries observable for real.** Have `parse_with_retry` also record the *reason* each
   attempt failed (`enum`, `missing`, `semantic`) into `METRICS`. Feed mixed bad outputs and
   read the breakdown.
3. **Tighten the semantic guard.** Add a rule: `needs_human` must be `True` whenever
   `severity` is `high` or `critical`. Predict which of the canned outputs now fail, then run.
4. **Prove the budget cap holds.** Feed `complete_structured` a list of three never-valid
   responses with `attempts=2`. Predict the final `METRICS["attempts"]` *before* running, then
   confirm the cap — not the input length — bounds the work."""))

cells.append(code('# Exercise 1 - add a simpler-contract fallback tier before the human queue.\n'))
cells.append(code('# Exercise 2 - record per-attempt failure reasons into METRICS.\n'))
cells.append(code('# Exercise 3 - require needs_human=True for high/critical; predict the failures.\n'))
cells.append(code('# Exercise 4 - prove attempts are capped, not driven by input length.\n'))

cells.append(md(
"""## Next

You built the toy; here's where the real one lives.

- **Capstone choke point →** [`../../../capstone/llm/structured.py`](../../../capstone/llm/structured.py)
  — the production `complete_structured()` (checkpoint `checkpoints/ch15-structured`). From
  here on, **every** model call in Parts VI–VIII goes through it; no capstone code parses raw
  model text.
- **Forward links:** **Ch 22** (evals — the statistical safety net these contracts make crisp),
  **Ch 23** (observability — instruments this exact choke point), **Ch 29** (the reliability
  primitives: timeouts, retries, idempotency, circuit breakers applied to the model as an
  unreliable dependency).
- **Book:** **§15.2–§15.4** for the full treatment, including the variance-control checklist."""))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open("15-02-validate-retry-repair-degrade.ipynb", "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print("wrote 15-02, cells:", len(cells))
