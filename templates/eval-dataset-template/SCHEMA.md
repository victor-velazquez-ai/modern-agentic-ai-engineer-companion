# Dataset schema — one case per line (JSONL)

This file is the **contract** for every row in `datasets/*.jsonl`. The CI guard
[`tests/test_schema.py`](tests/test_schema.py) enforces it, so keep this doc and the test in
sync: if you add a field, document it here *and* update the test.

One case = one line of JSON. JSONL (not a JSON array) because it is **appendable** (add a case
without rewriting the file), **diff-able** (a new case is a one-line diff a reviewer can read),
and **streamable** (you can load a million rows without holding them all in memory).

## Fields

| Field      | Type            | Required | Description |
|------------|-----------------|----------|-------------|
| `id`       | string          | ✅       | Stable, unique identifier for the case. Never reuse or renumber — scores are tracked by `id` over time. Convention: `<set>-<NNN>`, e.g. `golden-001`, `adv-001`. |
| `input`    | string \| object | ✅       | What you feed the system under test. A bare prompt string, or an object (`{"messages": [...]}`, tool args, etc.) — whatever your `target()` consumes. |
| `expected` | string \| object \| null | ✅ | The reference answer / the property to check. For `must-refuse` cases this is often a short note like `"refusal"`; for open-ended cases it can be a rubric the LLM-judge reads. May be `null` when the check is purely structural. |
| `tags`     | array of strings | ✅ (≥1) | Slices for reporting (see below). **Every case must carry at least one tag.** |
| `notes`    | string          | optional | Free-text: why this case exists, the bug it pins, links. Empty string is fine. |

## Tag convention

Tags are **first-class** — they let you report per-segment scores ("we pass 95% overall but only
60% on `multi-step`") instead of a single opaque accuracy number. Use lowercase, hyphenated tags.
Mix at least one tag from each axis that applies:

- **Capability** — *what* the case exercises: `retrieval`, `tool-use`, `multi-step`, `reasoning`,
  `summarization`, `extraction`, `formatting`.
- **Difficulty** — `easy`, `medium`, `hard`.
- **Safety** — `must-refuse` (the system *should* decline), `permission-probe`,
  `injection` (prompt-injection attempt). These live mostly in `adversarial.jsonl`.
- **Provenance** — `regression` plus the ticket, e.g. `regression`, `ticket-1234`. Add these the
  day you turn a production bug into a permanent test.

There is no fixed enum — add tags as your suite grows. `test_schema.py` only enforces "≥ 1 tag";
keeping the *vocabulary* tidy is a review-time habit, not a hard rule.

## Example row (pretty-printed; store as one line)

```json
{
  "id": "golden-001",
  "input": "What is the capital of France?",
  "expected": "Paris",
  "tags": ["retrieval", "easy"],
  "notes": "Smoke test: trivial factual lookup."
}
```

## Conventions

- **No secrets, no PII.** Datasets are committed to git. Never put API keys, tokens, real
  customer data, or anything you would not paste into a public PR. (Synthetic data only.)
- **`id` is immutable.** Edit `input`/`expected`/`tags` freely; never change an `id` once it
  exists, or you lose its score history.
- **One concern per case.** If you are tempted to assert two unrelated things, write two cases.
