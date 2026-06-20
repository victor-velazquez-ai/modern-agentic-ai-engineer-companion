# Template — Prompt Template (versioned)
> Realizes book Ch 10 · Status: 📋 planned (Phase 1)

## What it scaffolds
A versioned-prompt layout that takes prompts out of inline f-strings and into reviewable,
testable files: separate system/user templates, a small registry that loads a *named,
versioned* prompt, and a render + regression test.

## When to copy it
You have prompts worth treating as code — you want to diff changes, pin a version in
production, A/B two variants, and not break a downstream parser when you reword the system
message. Copy this into your repo's `prompts/` directory.

## Planned file tree
```text
prompt-template/
├── README.md                  # the versioning rule + "copy me" usage
├── registry.py                # load(name, version="latest") → rendered messages; lists versions
├── prompts/
│   └── support_reply/         # one folder per prompt (▢ rename to your prompt)
│       ├── meta.yaml          # name, owner, description, latest version, model + params
│       ├── v1/
│       │   ├── system.md      # system template — {{variables}} as placeholders
│       │   └── user.md        # user template — {{variables}}
│       └── v2/                # a second version, to show diffing/rollback
│           ├── system.md
│           └── user.md
└── tests/
    ├── test_render.py         # placeholders fill; unknown/missing var fails loudly
    └── test_registry.py       # load() resolves "latest" + a pinned version deterministically
```

## Defaults baked in
- **Files, not f-strings:** prompts are Markdown so they review well; variables are explicit
  `{{placeholders}}` rendered by the registry (no silent missing-var bugs).
- **Versioning convention:** `vN/` folders, immutable once shipped; `meta.yaml` records the
  `latest` pointer plus the model id and sampling params the prompt was tuned for.
- **Registry, not magic:** `load(name, version)` returns the assembled message list; pinning a
  version in prod is one argument; rollback is changing one line.
- **Tested:** rendering with the wrong/absent variable raises; "latest" resolves
  deterministically, so prompt changes are caught by CI like any other code.
- **No secrets:** prompts contain no keys; example variables are placeholders, never real data.
- **Model default:** `meta.yaml` records the latest, most capable Claude model the prompt targets.

## Maps to the book
- **Ch 10 — Prompt Engineering:** turns the chapter's techniques and "test your prompts" point
  into a concrete, version-controlled artifact (the 🔧 prompt-testing Build).
- **Notebook:** the [`learn/part-03-…/10-prompt-engineering/`](../../learn/) walkthroughs build
  prompts that graduate into this layout. **Blueprint/Capstone:** this is where
  [`../../blueprints/llm-gateway/`](../../blueprints/llm-gateway/PLAN.md) and the capstone
  `llm/` layer read their prompts from, so prompt edits don't touch code.

## Phase-2 definition of done
- [ ] `registry.load("support_reply")` returns rendered messages; pinning `v1` vs `v2` differs.
- [ ] `make test` passes: missing-variable raises; "latest" resolution is deterministic.
- [ ] Two versions present to demonstrate diff/rollback; example vars are placeholders only.
- [ ] No secrets or real customer data committed in any prompt file.
