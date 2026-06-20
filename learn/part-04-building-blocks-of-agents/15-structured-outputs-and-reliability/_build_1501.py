"""Generator for notebook 15-01. Run once, then it can be deleted."""
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
"""# Contract first, then make the model obey

> \U0001F4D3 *Companion to* **Modern Agentic AI Engineer** *· Ch 15 §15.1–§15.2 · type: walkthrough*

**The promise:** define an extraction contract as a Pydantic model, get a *validated, typed*
object back from the model in a single call via constrained decoding — and know exactly when
the call still hands you "no result."

This is notebook **15-01**. It runs **free and offline** by default
(`COMPANION_MOCK=1`), with canned-but-realistic responses; flip to a live key only when you
want to see the real round trip."""))

cells.append(md(
"""## \U0001F9E0 Why this matters

The instant a model's output is *parsed by a program* instead of read by a human, every
quirk of free text becomes a crash: a missing brace, a chatty preamble, a field renamed on a
whim, an enum value the model invented because it sounded plausible. Most production LLM
calls are exactly this kind of call.

The fix is the same one you already use for any integration: **write the contract first.**
In Python that contract is a single Pydantic model — and because Pydantic v2 compiles to
JSON Schema, that one artifact is simultaneously your *prompt documentation*, your *decoding
constraint*, your *validator*, and your *typed interface* into the rest of the codebase. One
object, four jobs."""))

cells.append(md(
"""## Objectives & prereqs

**By the end you can:**
- write a model-*friendly* extraction schema (flat, enum-constrained, with an escape hatch);
- inspect the JSON Schema a Pydantic model generates and see why each choice matters;
- get a typed, validated object back in one call via constrained decoding; and
- handle the "guaranteed shape, *still* no result" case correctly.

**Prereqs:** Ch 4 (typing / Pydantic) · Ch 11 (model APIs & SDK shapes) · Ch 12 (tool
schemas — the same JSON-Schema lingua franca). Run the **Setup** cell first."""))

cells.append(code(
'''import json
import os
import random
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv()  # read keys/flags from a local .env if present

# MOCK=1 (default) -> canned, deterministic, free, offline.
# MOCK=0 -> hit the live Anthropic API (needs ANTHROPIC_API_KEY; costs ~a few short calls).
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(15)  # any stochastic choice below is reproducible

DATA = Path("data")

print(f"MOCK mode: {MOCK}  (set COMPANION_MOCK=0 in .env to hit the live API)")
if not MOCK and not os.getenv("ANTHROPIC_API_KEY"):
    raise RuntimeError(
        "MOCK=0 but ANTHROPIC_API_KEY is not set. "
        "Add it to .env, or set COMPANION_MOCK=1 to run free and offline."
    )'''))

cells.append(md(
"""## 1 · Write the contract — `TicketTriage`

This is the chapter's schema verbatim. Read it as four design decisions, not five fields:

- **`severity` is an enum, not a string.** A closed set turns a hallucination
  (`"urgent"`) into a *catchable validation error* instead of a silent bad value.
- **Every field has a `description`.** Those descriptions are *prompt text* — the model
  reads them. Write them with the care you'd give a system prompt.
- **`confidence` is bounded `0–1`.** It's the model's self-assessed certainty, which we'll
  use as a routing signal.
- **`needs_human`** is the model's in-contract escape hatch (more on that below)."""))

cells.append(code(
'''from enum import StrEnum


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketTriage(BaseModel):
    """Structured triage of an inbound support message."""

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


TicketTriage'''))

cells.append(md(
"""## 2 · One model, four jobs — inspect the generated JSON Schema

You wrote Python; the provider, your tools (Ch 12), and your validators all speak **JSON
Schema**. Pydantic bridges them for free. Look at what `TicketTriage` *becomes* — this exact
document is what constrained decoding enforces and what your field descriptions ship inside."""))

cells.append(code(
'''schema = TicketTriage.model_json_schema()
print(json.dumps(schema, indent=2))'''))

cells.append(md(
"""Notice three things in that dump:

- **`$defs.Severity.enum`** is the closed set `["low","medium","high","critical"]` — the
  model literally cannot emit anything else under constrained decoding.
- The **`description`** strings rode along into the schema. They *are* the field-level prompt.
- `confidence` carries **`minimum: 0` / `maximum: 1`** — but read the ⚠️ pitfall later for
  the catch on who actually enforces those bounds."""))

cells.append(code(
'''print("Severity is a closed set:", schema["$defs"]["Severity"]["enum"])
print("confidence bounds in schema:",
      schema["properties"]["confidence"].get("minimum"),
      "..",
      schema["properties"]["confidence"].get("maximum"))
print("required fields:", schema["required"])'''))

cells.append(md(
"""## 3 · Design *for the model*, not for your database

A schema that mirrors your domain model is a schema the model fills out badly. The rules of
thumb, each demonstrated by the contract above:

| Do | Why |
|---|---|
| **Flat > nested** | every level of nesting is another place to drop a brace |
| **Enums > free strings** (closed sets) | converts hallucination into a validation error |
| **Describe every field** | descriptions are prompt text the model actually reads |
| **A handful of fields > an exhaustive mirror** | the model triages; it isn't your ORM |

Watch the enum do its job — feed Pydantic an invented severity and a closed set catches it:"""))

cells.append(code(
r'''# An enum turns "the model made something up" into a clean, catchable error.
try:
    TicketTriage(
        summary="Login is down for everyone.",
        severity="urgent",          # not a member of Severity
        product_area="auth",
        needs_human=True,
        confidence=0.9,
    )
except ValidationError as exc:
    print("Caught an invented enum value before it could reach your code:\n")
    print(exc)'''))

cells.append(md(
"""## \U0001F4A1 The escape hatch — let the model say "I'm not sure"

Give every extraction schema a way to express *uncertainty inside the contract*: a
`confidence` score, a nullable field ("use null when the document doesn't say"), or an
explicit `"unknown"` enum member. Without one, you've made **guessing mandatory** — the model
*must* put something in each field, so it will, and it'll be confident-shaped nonsense.

`TicketTriage` has two such hatches: `confidence` (a number you can threshold on) and
`needs_human` (a boolean the model sets to hand the item off). They're why the model can be
honest instead of forced to invent."""))

cells.append(md(
r"""## 4 · 🔧 Climb the ladder — from polite request to guarantee

There's a ladder of techniques for making the model actually produce the shape. Climb only as
high as you need:

1. **Prompting** — describe the schema, ask for "JSON only." Fine for a notebook; on a long
   tail of inputs it drifts (prose, dropped fields, almost-JSON). *Never ship as the only
   layer.*
2. **Constrained decoding** ← *we use this.* The provider samples every token from the subset
   that keeps the output a valid prefix of schema-conformant JSON, so a malformed shape is not
   discouraged but **unrepresentable**.
3. **Validate-and-retry with feedback** — the fallback when decoding is unavailable or a rule
   is semantic. *(Built in notebook 15-02.)*
4. **Repair** — deterministic normalization as a pre-parse step. *(Also 15-02.)*

We'll do **rung 2** now: the SDK round trip is one call — Pydantic in, validated Pydantic out."""))

cells.append(md(
r"""### The live round trip (rung 2)

This is the book's `§15.2` code. In `MOCK=0` it runs for real; we keep it in its own
function so the rest of the notebook stays offline.

```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.parse(
    model="claude-opus-4-8",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": f"Triage this support message:\n\n{raw_message}",
    }],
    output_format=TicketTriage,        # the Pydantic model *is* the contract
)
triage: TicketTriage = response.parsed_output
```

Pydantic model in, validated `TicketTriage` out, in a single call. Below we wrap it so
`MOCK=1` returns a canned-but-realistic object instead."""))

cells.append(md(
"""### A tiny corpus of inbound messages

Five sample support messages live in `data/support_messages.json`. One of them (`msg-004`,
just `"hi"`) is *deliberately* content-free — we'll use it for the prediction below."""))

cells.append(code(
'''messages = json.loads((DATA / "support_messages.json").read_text(encoding="utf-8"))
for m in messages:
    preview = m["text"] if len(m["text"]) <= 80 else m["text"][:77] + "..."
    print(f'{m["id"]} [{m["channel"]:>6}]  {preview}')'''))

cells.append(code(
r'''# --- The structured-extraction call, with a mock path that mirrors the real one. ---
# Both paths return EITHER a validated TicketTriage OR None ("no result").

# Canned, realistic responses for MOCK mode (deterministic).
_CANNED: dict[str, TicketTriage | None] = {
    "msg-001": TicketTriage(
        summary="All users are locked out; the dashboard returns a 500 error.",
        severity=Severity.CRITICAL, product_area="dashboard",
        needs_human=True, confidence=0.93,
    ),
    "msg-002": TicketTriage(
        summary="CSV export on the Reports page has its columns in the wrong order.",
        severity=Severity.LOW, product_area="reports",
        needs_human=False, confidence=0.74,
    ),
    "msg-003": TicketTriage(
        summary="Customer was double-charged for the October subscription and wants a refund.",
        severity=Severity.MEDIUM, product_area="billing",
        needs_human=True, confidence=0.9,
    ),
    "msg-004": None,  # "hi" - not enough signal to triage
    "msg-005": TicketTriage(
        summary="Vague follow-up with no specifics about the original issue.",
        severity=Severity.LOW, product_area="unknown",
        needs_human=True, confidence=0.35,
    ),
}


def triage_message(raw_message: str, message_id: str | None = None) -> TicketTriage | None:
    """Return a validated TicketTriage, or None when the model produced no usable result."""
    if MOCK:
        # Deterministic stand-in for client.messages.parse(...).
        return _CANNED.get(message_id, None)

    # --- live path (rung 2: constrained decoding) ---
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.parse(
        model="claude-opus-4-8",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"Triage this support message:\n\n{raw_message}",
        }],
        output_format=TicketTriage,
    )
    # A refusal or a max_tokens truncation can leave no object - handle it.
    return getattr(response, "parsed_output", None)


# Triage the clear-cut critical one.
critical = triage_message(messages[0]["text"], messages[0]["id"])
print(type(critical).__name__)
print(critical.model_dump_json(indent=2))'''))

cells.append(md(
"""You got a fully **typed** `TicketTriage` back — `critical.severity` is a `Severity`
enum, `critical.confidence` is a `float`, and your IDE autocompletes all of it. No
`json.loads`, no `KeyError`, no "did the model spell the field right?" The contract did that."""))

cells.append(md(
"""## \U0001F52E Predict, then run

`msg-004` is just `"hi"`. Constrained decoding *guarantees the shape* of any object it
returns — so:

**Question:** when we triage a content-free message, do we get back a perfectly-shaped (but
guessed) `TicketTriage`, or can the call legitimately return **no result**?

Write your guess down, then run the next cell."""))

cells.append(code(
'''empty = messages[3]            # msg-004, text == "hi"
result = triage_message(empty["text"], empty["id"])

if result is None:
    print("NO RESULT - the call returned nothing parseable for:", repr(empty["text"]))
    print("Your code MUST handle this branch even though the *shape* was guaranteed.")
else:
    print("Got an object:", result.model_dump_json(indent=2))'''))

cells.append(md(
"""**What you just saw.** A guaranteed *shape* is not a guaranteed *result*. A safety refusal,
a `max_tokens` truncation, or simply too little signal can all leave you with no object. The
guarantee is "if you get JSON, it conforms" — never "you always get JSON." (`msg-005`, the
vague follow-up, shows the other honest move: the model *does* answer, but with low
`confidence` and `needs_human=True` — uncertainty expressed *inside* the contract.)"""))

cells.append(md(
"""## ⚠️ Pitfall — read the fine print on the "guarantee"

Constrained decoding is powerful but bounded. Three sharp edges:

- **Restricted schema features.** No recursion; some keyword combinations aren't supported.
  Keep schemas flat (you already do).
- **Numeric bounds may be validated *client-side*.** `ge=0, le=1` on `confidence` is typically
  enforced by *Pydantic after the fact*, not inside the decoder — so a model can emit
  `confidence: 1.4`, and it's `model_validate` that rejects it, not the sampler.
- **"No object" is always possible.** Refusal or truncation → no result, as you just saw.

The takeaway: **calling code handles `None` even when the shape is guaranteed.** Watch the
client-side bound actually fire:"""))

cells.append(code(
r'''# The decoder constrains the SHAPE; Pydantic enforces the BOUNDS. Different layers.
raw_from_model = '{"summary": "x", "severity": "low", "product_area": "api", "needs_human": false, "confidence": 1.4}'
try:
    TicketTriage.model_validate_json(raw_from_model)
except ValidationError as exc:
    print("Shape was fine; the 0..1 BOUND was caught client-side by Pydantic:\n")
    print(exc)'''))

cells.append(md(
"""## \U0001F3AF Senior lens — the schema is an API contract; version it like one

Downstream code, prompts, *and* evals (Ch 22) all couple to `TicketTriage`. Renaming a field
or tightening an enum is a breaking change with the same blast radius as editing a public API
response — it can silently invalidate cached outputs, break the eval set's golden answers, and
desync the prompt that describes the fields.

So treat schema changes with API ceremony: version them, review them, and migrate consumers
deliberately. The junior writes the schema once and edits it casually; the senior knows the
schema *is* the integration surface, and that everything hangs off its stability."""))

cells.append(md(
"""## Recap

- **Contract first.** One Pydantic model is your prompt docs, decoding constraint, validator,
  and typed interface — four jobs, one artifact.
- **Design for the model:** flat over nested, **enums over free strings**, a `description` on
  every field, and an **escape hatch** (`confidence`, nullable, `needs_human`) so the model
  can be honest instead of forced to guess.
- **Constrained decoding (rung 2)** makes a malformed shape *unrepresentable* and gives you a
  typed object in one call: Pydantic in, validated Pydantic out.
- **A guaranteed shape is not a guaranteed result** — handle `None`. And numeric bounds are
  enforced *client-side*, so validation still has a job.
- **Version the schema like an API contract** — prompts, code, and evals all couple to it."""))

cells.append(md(
"""## Exercises

Each one *changes* something and asks you to predict the result first. Solutions land in
`solutions/` (Phase 2) — don't peek until you've run your version.

1. **Add an escape-hatch enum.** Add an `"unknown"` member to `Severity` (or a separate
   `product_area` enum with `"unknown"`). Re-generate the JSON Schema and predict: does the
   model now have a *legal* way to decline? Update one canned response to use it.
2. **Break the bound on purpose.** Construct a `TicketTriage` with `confidence=2.0` and predict
   which layer rejects it (decoder or Pydantic) before you run it.
3. **Tighten the contract.** Add a `model_config = ConfigDict(extra="forbid")` and feed the
   validator a JSON object with one extra key. Predict whether it's accepted, then confirm.
4. **A second escape hatch.** Make `product_area` `str | None` with a description telling the
   model to use `null` when unsure. Re-triage `msg-005` (the vague follow-up) in your head:
   what *should* a good model put there now?"""))

cells.append(code('# Exercise 1 - add an "unknown" Severity member and re-inspect the schema.\n'))
cells.append(code('# Exercise 2 - predict which layer rejects confidence=2.0, then construct it.\n'))
cells.append(code('# Exercise 3 - forbid extra keys and feed an object with an unexpected field.\n'))
cells.append(code('# Exercise 4 - make product_area nullable with a "use null when unsure" description.\n'))

cells.append(md(
"""## Next

You can now define a model-friendly contract and get a typed, validated object back — while
correctly handling "no result." But constrained decoding isn't available everywhere, it
doesn't enforce *semantic* rules, and even a perfectly-shaped object can be *wrong*.

- **Next notebook → [`15-02-validate-retry-repair-degrade.ipynb`](./15-02-validate-retry-repair-degrade.ipynb)** —
  build `complete_structured()`: validate-and-retry with error feedback, repair as
  normalization, semantic guards, bounded+counted retries, and designed degradation paths.
- **This feeds the capstone choke point →** [`../../../capstone/llm/structured.py`](../../../capstone/llm/structured.py)
  (`checkpoints/ch15-structured`). After it, *no* capstone code parses raw model text.
- **Book:** revisit **§15.1–§15.2** for the full ladder discussion."""))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open("15-01-schema-first-constrained-decoding.ipynb", "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print("wrote 15-01, cells:", len(cells))
