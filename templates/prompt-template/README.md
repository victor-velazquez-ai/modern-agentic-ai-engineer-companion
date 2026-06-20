# prompt-template — versioned prompts as code

A copy-into-your-job scaffold that takes prompts **out of inline f-strings** and
into reviewable, testable files: separate `system` / `user` templates, a small
registry that loads a *named, versioned* prompt, and render + regression tests.

> Realizes book Ch 10 (Prompt Engineering). This is the 🔧 prompt-testing Build:
> the chapter's "treat your prompts like code, and test them" point, made concrete.

## When to copy it

You have prompts worth treating as code — you want to **diff** changes, **pin** a
version in production, **A/B** two variants, and not silently break a downstream
parser when you reword the system message. Copy this into your repo's `prompts/`
directory (or copy the whole folder and keep `registry.py` next to `prompts/`).

## What you get

```text
prompt-template/
├── README.md                  # you are here
├── registry.py                # load(name, version="latest") -> rendered messages
├── prompts/
│   └── support_reply/         # one folder per prompt (rename to your prompt)
│       ├── meta.yaml          # name, owner, description, latest pointer, model + params
│       ├── v1/
│       │   ├── system.md      # system template — {{variables}} as placeholders
│       │   └── user.md        # user template — {{variables}}
│       └── v2/                # a second version, to show diff / rollback
│           ├── system.md
│           └── user.md
└── tests/
    ├── test_render.py         # placeholders fill; unknown/missing var fails loudly
    └── test_registry.py       # load() resolves "latest" + a pinned version deterministically
```

## Copy and use

```bash
# 1. copy the scaffold into your project (you own it now — not a submodule)
cp -r templates/prompt-template ~/work/my-agent/prompts-kit
cd ~/work/my-agent/prompts-kit

# 2. install the one dependency the registry needs
pip install pyyaml          # plus `pytest` to run the tests

# 3. find every placeholder and replace it
grep -rn "TODO" .           # owner email, your product voice, your variables

# 4. confirm it works before you add anything
python registry.py          # prints the rendered example prompt
pytest -q                   # render + registry tests must pass
```

Then make it yours: rename `prompts/support_reply/` to your prompt, rewrite the
`system.md` / `user.md` bodies, update the placeholders, and point `meta.yaml` at
your owner + model.

## Using the registry in code

```python
import registry

rendered = registry.load(
    "support_reply",               # prompt name (the folder under prompts/)
    "latest",                      # or pin: "v1" / "v2"
    variables={
        "company_name": "Acme Co.",
        "agent_name": "Sam",
        "customer_name": "Jordan",
        "customer_message": "Where is my order?",
        "tone": "warm and concise",
    },
)

# Hand straight to the Claude Messages API — model + params come from meta.yaml.
from anthropic import Anthropic

client = Anthropic()                # reads ANTHROPIC_API_KEY from the environment
resp = client.messages.create(
    model=rendered.model,                       # "claude-opus-4-8"
    max_tokens=rendered.params["max_tokens"],
    thinking=rendered.params["thinking"],       # {"type": "adaptive"}
    output_config={"effort": rendered.params["effort"]},
    system=rendered.system,
    messages=rendered.messages,
)
```

> Note: on Claude Opus 4.8 / 4.7, `temperature` / `top_p` / `top_k` are **not**
> accepted (they 400). Thinking is adaptive-only. That's why `meta.yaml` records
> `effort` and adaptive `thinking` rather than a sampling temperature — steer the
> model through the prompt text and the effort level.

## The conventions baked in

- **Files, not f-strings.** Prompts are Markdown so they review well in a PR.
  Variables are explicit `{{placeholders}}` rendered by the registry — there is
  **no silent missing-var bug**: an unsupplied placeholder *or* an unused
  variable raises.
- **Versioning rule.** `vN/` directories are **immutable once shipped**. To
  change a shipped prompt, add `vN+1/` and move the `latest:` pointer in
  `meta.yaml`. **Rollback is changing that one line back.**
- **`meta.yaml` is the source of truth** for the `latest` pointer plus the model
  id and the sampling/effort params the prompt was tuned for. Pinning a version
  in prod is one argument to `load()`.
- **Model default.** `meta.yaml` targets the latest, most capable Claude model
  (`claude-opus-4-8`). Swap to a `claude-sonnet-*` / `claude-haiku-*` id for
  cheaper, high-volume tiers.
- **Tested.** `pytest` proves rendering catches bad variables and that "latest"
  resolves deterministically — so a prompt change is caught by CI like any code.
- **No secrets.** Prompt files contain no keys; example variable values are
  placeholders, never real customer data. The registry reads files only — no
  network calls, no business logic.

## Definition of done (after you fill the TODOs)

- [ ] `registry.load("<your-prompt>")` returns rendered messages; pinning two
      versions differs.
- [ ] `pytest -q` passes: missing-variable raises; "latest" is deterministic.
- [ ] Two versions present to demonstrate diff / rollback.
- [ ] No secrets or real customer data committed in any prompt file.

## Where this fits in the companion repo

The `learn/.../10-prompt-engineering/` notebooks build prompts that graduate into
this layout. The `blueprints/llm-gateway/` and the capstone's `llm/` layer read
their prompts from a structure like this one, so a prompt edit never touches code.
