# `prompts/` — versioned prompt registry

The platform keeps prompts as **versioned templates on disk**, loaded through a
small registry, so a prompt is a *tracked artifact* — diffable, reviewable,
pinnable, A/B-able — not a string buried in code. This is the foundation for the
"pin a prompt + tool + model triple" discipline Ch 44 formalizes. Built in
**Ch 10** (§10 Build); the copy-into-your-job version is the
[`prompt-template`](../../../templates/prompt-template/README.md) template.

> Extends Appendix C: Appendix C implies prompts live with the model layer; Ch 10
> calls out a dedicated `prompts/` directory + registry. Reference, not a starting
> point — build yours from the chapter and compare.

## Layout (one directory per prompt)

```text
prompts/
├── __init__.py            # re-exports the registry API
├── registry.py            # load(name, version="latest") -> RenderedPrompt
└── triage_ticket/         # an example prompt (rename/add your own)
    ├── meta.yaml          # name, owner, description, `latest` pointer, model + params
    ├── v1/ {system.md, user.md}
    └── v2/ {system.md, user.md}   # a second version → shows diff / rollback
```

## The rules it encodes

- **A prompt is files, not an f-string.** `system.md` / `user.md` use `{{variable}}`
  placeholders; `meta.yaml` records the owner, the model + params the prompt was
  tuned for, and the `latest` pointer.
- **Versions are immutable.** A shipped `vN/` is never edited. To change a prompt,
  add `vN+1/` and move `latest` in `meta.yaml`. **Rollback is moving one line back.**
- **`latest` resolves deterministically** — from the `meta.yaml` pointer, not
  "whatever sorts highest on disk."
- **Loud failures.** A missing placeholder or an unused supplied variable raises,
  so a reworded template can't silently break a call site.

## Using it

```python
from prompts import load
from llm import complete_structured
from pydantic import BaseModel

class Triage(BaseModel):
    category: str
    priority: str
    confidence: float
    rationale: str

p = load("triage_ticket", "latest", variables={
    "product_name": "Acme Platform",
    "categories": "billing, bug, feature_request, account",
    "ticket_text": "I was charged twice this month.",
})
# p.system / p.messages / p.model / p.params — feed straight into the model layer.
result = complete_structured(
    p.messages[0]["content"], Triage, system=p.system, model=p.model
)
result.value          # a validated Triage
```

Smoke-test the registry directly: `python registry.py` renders the example prompt
and prints what would go to the model (reads files only — safe, no spend).

## Notes

- The registry reads files and substitutes variables — **no business logic, no
  network, no secrets.** Example variable values are placeholders, never real data.
- `meta.yaml` is parsed with **PyYAML when installed**, falling back to a tiny
  built-in parser for these flat files so the registry runs with no extra
  dependency (the repo's mock-first stance). Install PyYAML for richer metadata.
- The example `triage_ticket` prompt pairs with `llm.complete_structured`: it asks
  for JSON and the model layer validates it. v1 → v2 shows a real version bump
  (priority rubric + confidence added) you can diff and roll back.
