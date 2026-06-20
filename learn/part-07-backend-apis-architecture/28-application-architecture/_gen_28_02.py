"""Generator for 28-02-config-di-and-feature-flags.ipynb. Not shipped; run once."""
import json
from pathlib import Path

OUT = Path(__file__).parent / "28-02-config-di-and-feature-flags.ipynb"

cells = []


def md(text):
    cells.append(("markdown", text))


def code(text):
    cells.append(("code", text))


md("""# 12-Factor Config, the Composition Root, and Dark Launches

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 28 §28.3–28.5 · type: walkthrough*  🔧 *This is the chapter's Build.*

In 28-01 you isolated the domain behind a port. Now you'll **wire** it the production
way: load **typed config from the environment** (12-factor), assemble the adapters at a
single **composition root**, override a dependency in a test, and flip behavior with a
**feature flag** — shipping a change *dark* and rolling it out (and back) by percentage,
with no redeploy.""")

md("""## 🧠 Why this matters

The architectures from 28-01 only work if something **wires the adapters to the core**.
Two disciplines make that wiring safe:

- **Config in the environment (12-factor).** Never hard-code anything that differs
  between environments — URLs, credentials, limits, flags. Read it from the environment
  so the *same build* runs in dev, staging, and prod. Typed config (Pydantic Settings)
  makes it validated and **fail-fast**: a missing required var stops the process at
  startup, not at 3 a.m. in a handler.
- **Dependency injection at one composition root.** A component declares what it needs
  and is *given* it; one place — the composition root — decides the concrete adapter.
  That keeps the core ignorant of implementations and makes tests trivial (override the
  factory; no patching, no globals).

On top of that, **feature flags decouple deploy from release**. Code ships dark and you
turn it on for 1% of traffic, then 10%, then everyone — and turn it *off* instantly if
metrics dip. For probabilistic AI features, whose quality is only fully visible in
production, expanding or retracting by percentage is how you ship safely.""")

md("""## Objectives & prerequisites

**By the end you can:**

- Define typed config with `pydantic-settings` (`BaseSettings`, `env_prefix`) and watch
  it **fail fast** when a required variable is missing.
- Read a secret from `os.environ` and explain why the hardcoded alternative leaks to git
  and logs (and where real secrets belong: a secret manager, with rotation).
- Build a **composition root** — `get_store()` / `get_service()` factories in the
  FastAPI `Depends` shape — and **override** a dependency in a test with a fake.
- Implement a **percentage feature flag** that routes traffic to a new vs. baseline
  implementation deterministically per user, and roll it out and back with no code change.

**Prereqs:** 28-01 (ports & adapters). `pydantic` and `pydantic-settings` come with
`pydantic` in `requirements.txt`.

**Run first:** the Setup cell. Fully **offline**: the LLM "planner" behind the flag is a
mock callable, so the notebook is free and deterministic in any mode.""")

code('''# --- Setup -------------------------------------------------------------------
import hashlib
import os
import random

from dotenv import load_dotenv

load_dotenv()  # loads a local .env IF present; never commit real secrets

# This notebook is offline: the "planner" behind the feature flag is a mock callable,
# so MOCK=1 (default) or MOCK=0 both run free. We keep the switch for consistency and
# to demonstrate the fail-fast secret check without ever needing a real key.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(28)  # determinism for the rollout sampling below

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    _HAVE_PS = True
except ImportError:  # pydantic v1 fallback so the notebook still runs everywhere
    from pydantic import BaseSettings  # type: ignore
    SettingsConfigDict = dict  # type: ignore
    _HAVE_PS = False

print("Offline config/DI/flags lab. No API key needed; nothing is billed.")
print("pydantic-settings available:", _HAVE_PS)''')

md("""## 1 · Typed config from the environment, with a safe default

`Settings` reads from the environment (optionally a local `.env`) under a prefix, so a
deployment sets `APP_DATABASE_URL`, `APP_MAX_AGENT_STEPS`, etc. Fields **without
defaults are required**; fields **with defaults** are safe overrides per environment.
The same build, configured differently, runs everywhere.

We point `env_prefix="APP_"` so the demo can't collide with unrelated env vars on your
machine.""")

code('''class Settings(BaseSettings):
    """Typed, validated application config sourced from the environment.

    Required (no default): database_url. Optional (safe default): max_agent_steps,
    new_planner_rollout_pct. Secrets (anthropic_api_key) default to "" so the app can
    boot in MOCK/offline mode; in prod they come from the environment / a secret
    manager, never from code.
    """

    if _HAVE_PS:
        model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env",
                                          extra="ignore")
    else:  # pydantic v1
        class Config:  # type: ignore
            env_prefix = "APP_"

    database_url: str = "sqlite+aiosqlite:///:memory:"  # safe local default
    anthropic_api_key: str = ""                          # secret: from env, not code
    max_agent_steps: int = 12                            # bounded by default
    new_planner_rollout_pct: int = 0                     # flag starts fully OFF


# Configure the demo deterministically via the environment (as a deployment would).
os.environ["APP_MAX_AGENT_STEPS"] = "8"

settings = Settings()  # fails fast at construction if a REQUIRED var were missing
print("database_url     :", settings.database_url)
print("max_agent_steps  :", settings.max_agent_steps, "(overridden via APP_MAX_AGENT_STEPS)")
print("rollout_pct      :", settings.new_planner_rollout_pct)''')

md("""## 2 · Fail fast: a required variable that's missing

Make a setting **required** (no default) and watch what happens when its env var is
absent: construction raises immediately. That's the property you want — a misconfigured
service refuses to start, instead of limping into production and failing on the first
request. We use a throwaway subclass so we don't break `settings` above.""")

code('''from pydantic import ValidationError


class StrictSettings(Settings):
    # No default -> REQUIRED. If APP_SERVICE_NAME is unset, construction fails.
    service_name: str


os.environ.pop("APP_SERVICE_NAME", None)  # ensure it's missing
try:
    StrictSettings()
    print("constructed (unexpected)")
except ValidationError as exc:
    n = len(exc.errors())
    print(f"Fail-fast: refused to start, {n} validation error(s):")
    for e in exc.errors():
        print("  -", e["loc"], "->", e["msg"])

# Now provide it (as a deployment would) and it constructs cleanly.
os.environ["APP_SERVICE_NAME"] = "research-api"
print("with APP_SERVICE_NAME set:", StrictSettings().service_name)''')

md("""## 3 · 🔮 Predict: hardcoded secret vs. `os.environ`

Two ways to get an API key into the app are shown below. One reads it from
`os.environ`; the other hardcodes a literal.

**Predict before running:**
1. Which value would get committed to git and printed into your logs/tracebacks?
2. If you had to **rotate** the key tomorrow (revoke the old one), which approach lets
   you do it with no code change and no redeploy?

Then read the result and the note on secret managers.""")

code('''# Read from the environment: the value lives OUTSIDE the codebase. Nothing to commit;
# rotation is a deployment-side change (swap the env / secret-manager value, restart).
api_key_from_env = os.environ.get("APP_ANTHROPIC_API_KEY", "")  # empty in MOCK/offline
print("from env  : present?", bool(api_key_from_env), "(empty is fine offline)")

# Hardcoded literal: this STRING is now in git history, in every clone, and in any
# traceback that prints the module. This is the #1 most expensive incident in our field.
HARDCODED_KEY = "sk-ant-EXAMPLE-do-not-do-this"  # <-- never. (placeholder, not real)
print("hardcoded : leaks to git + logs:", HARDCODED_KEY[:10] + "...")

print(
    "\\nIn the cloud, secrets come from a SECRET MANAGER -- AWS Secrets Manager / SSM\\n"
    "Parameter Store, or HashiCorp Vault -- injected at runtime and ROTATED on a\\n"
    "schedule. The app reads them via the environment; it never embeds them. A .env\\n"
    "file is fine for LOCAL dev only, and must be gitignored."
)''')

md("""## ⚠️ Pitfall: committing `.env` — or shipping it *as* your prod secrets

A `.env` file is a local-dev convenience, **not** a production secrets mechanism. Two
failure modes bite teams constantly:

1. **Committing `.env`** — now every key is in git history forever (rotate them and scan
   history).
2. **Shipping `.env` to prod** as the way secrets arrive — instead fetch them from the
   secret manager at startup, or mount them as the platform intends.

The cell shows the *safe* artifact to commit: a `.env.example` with **placeholders
only**, documenting the variables without leaking any value.""")

code('''# This is the ONLY env artifact you commit: an EXAMPLE with no real values.
ENV_EXAMPLE = """\\
# .env.example -- copy to .env (which is gitignored) and fill in locally.
# In production these come from the secret manager, not this file.
APP_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/app
APP_ANTHROPIC_API_KEY=         # set locally; in prod inject from Secrets Manager/Vault
APP_MAX_AGENT_STEPS=12
APP_NEW_PLANNER_ROLLOUT_PCT=0
"""
print(ENV_EXAMPLE)

# A one-line guard you can run in CI: refuse to commit a real-looking key.
def looks_like_real_key(line: str) -> bool:
    val = line.split("=", 1)[1].strip() if "=" in line else ""
    return val.startswith("sk-") and len(val) > 12

leaks = [ln for ln in ENV_EXAMPLE.splitlines() if looks_like_real_key(ln)]
print("Lines that look like a leaked key:", leaks or "none -- safe to commit")''')

md("""## 4 · The composition root: one place decides the real adapter

Now dependency injection. Re-using the port and adapters from 28-01 (defined inline
here so this notebook is standalone), the **composition root** is the pair of factories
`get_store()` / `get_service()`. They have the exact **FastAPI `Depends` shape** — in a
real service you'd write `svc: ResearchService = Depends(get_service)` on a route — but
here we call them directly so the lesson stays framework-free.

The key property: **only `get_store()` names a concrete adapter.** Change one line there
and the whole app swaps stores.""")

code('''from typing import Protocol, runtime_checkable


@runtime_checkable
class DocumentStore(Protocol):
    async def search(self, query: str, k: int) -> list[str]: ...


class InMemoryStore:
    def __init__(self, docs: list[str]):
        self._docs = docs

    async def search(self, query: str, k: int) -> list[str]:
        terms = {t.lower() for t in query.split()}
        hits = [d for d in self._docs if any(t in d.lower() for t in terms)]
        return hits[:k]


class ResearchService:
    def __init__(self, store: DocumentStore):
        self._store = store

    async def answer(self, question: str, k: int = 3) -> str:
        passages = await self._store.search(question, k=k)
        return f"({len(passages)} passages) " + " | ".join(passages)


_FIXTURE = [
    "Refunds within 30 days to the original payment method.",
    f"Each agent run is capped at {settings.max_agent_steps} steps.",
]


# ----- composition root: the ONE place that wires concretes to the core -----
def get_store() -> DocumentStore:
    return InMemoryStore(docs=_FIXTURE)          # swap this single line to change stores


def get_service(store: DocumentStore | None = None) -> ResearchService:
    # In FastAPI: def get_service(store = Depends(get_store)). Same shape, no framework.
    return ResearchService(store or get_store())


import asyncio
print(asyncio.run(get_service().answer("refund", k=1)))''')

md("""## 5 · Override the dependency in a test — no patching, no globals

Because wiring lives behind factories, a test substitutes a **fake** by passing it in
(or, in FastAPI, via `app.dependency_overrides[get_store] = fake_store`). No
`unittest.mock.patch`, no monkeypatching module globals — just inject a different
implementation. This is the practical payoff of the composition root.""")

code('''class CannedStore:
    """A test double: returns a fixed, asserted-on passage. Offline + deterministic."""

    async def search(self, query: str, k: int) -> list[str]:
        return ["CANNED: deterministic test passage"][:k]


# "Override" by injecting the fake where get_store() would have run.
svc_under_test = get_service(store=CannedStore())
out = asyncio.run(svc_under_test.answer("anything", k=1))
print(out)
assert "CANNED" in out, "dependency override did not take effect"
print("test override worked: the core ran against the fake, untouched.")''')

md("""## 6 · Feature flag: ship dark, roll out by percentage

A flag decouples **deploy** from **release**. `flags.enabled("new_planner", user=...)`
routes a request to the new planner or the baseline. We make the decision
**deterministic per user** (hash the user id into 0–99 and compare to the rollout
percentage), so a given user has a *stable* experience and the rollout is reproducible —
not a coin flip on every request.

Both planners here are **mock callables** — no model, no network.""")

code('''def baseline_planner(task: str) -> str:
    return f"[baseline] step-by-step plan for: {task}"


def new_planner(task: str) -> str:
    return f"[new] outline-first plan for: {task}"


class Flags:
    """A tiny percentage-rollout flag store. State is an in-memory dict; in prod this
    is LaunchDarkly / a config service / a row in a table refreshed at runtime."""

    def __init__(self, rollout: dict[str, int] | None = None):
        self._rollout = rollout or {}

    def set_pct(self, name: str, pct: int) -> None:
        self._rollout[name] = max(0, min(100, pct))

    def enabled(self, name: str, user: str) -> bool:
        pct = self._rollout.get(name, 0)
        # Stable bucket 0..99 from (flag, user): same user -> same answer every call.
        h = hashlib.sha256(f"{name}:{user}".encode()).hexdigest()
        bucket = int(h, 16) % 100
        return bucket < pct


flags = Flags()
flags.set_pct("new_planner", settings.new_planner_rollout_pct)  # starts at 0% (dark)


def plan_for(task: str, user: str) -> str:
    if flags.enabled("new_planner", user=user):
        return new_planner(task)
    return baseline_planner(task)


# At 0%, every user gets the baseline -- the new code is shipped but DARK.
print(plan_for("summarize the refund policy", user="user-1"))''')

md("""## 7 · 🔮 Predict: turn the dial to 25%

We'll roll `new_planner` to **25%** and route 1,000 simulated users. Because bucketing
is deterministic per user, the *same* users flip to the new planner each run.

**Predict before running:**
1. Roughly what fraction of the 1,000 users will get `[new]` at 25%?
2. If you re-run the cell, will the *same* users get the new planner, or a fresh random
   set? Why does stability matter for a real rollout?""")

code('''flags.set_pct("new_planner", 25)

users = [f"user-{i}" for i in range(1000)]
new_count = sum(flags.enabled("new_planner", user=u) for u in users)
print(f"At 25%: {new_count}/1000 users routed to the NEW planner "
      f"(~{new_count/10:.1f}%).")

# Stability check: the SET of new-planner users is identical across calls (no re-roll).
set_a = {u for u in users if flags.enabled("new_planner", user=u)}
set_b = {u for u in users if flags.enabled("new_planner", user=u)}
print("Same users on every evaluation (stable rollout):", set_a == set_b)

# Instant rollback: drop to 0% -> everyone is back on baseline, no redeploy.
flags.set_pct("new_planner", 0)
print("After kill-switch -> new-planner users:",
      sum(flags.enabled("new_planner", u) for u in users))''')

md("""## 🎯 Senior lens: flags decouple deploy from release

Deploying code and releasing behavior are different events, and conflating them is how
teams ship scary changes. A flag lets you **deploy** the new planner to the whole fleet
while **releasing** it to 1% — then 10%, 50%, 100% — watching metrics at each step, with
an instant kill-switch if something dips.

For **probabilistic AI features** this is not optional polish. Quality is only fully
visible in production, so pair the percentage rollout with the **online evals** from Part
VI: expand the flag only while the new planner's eval scores and business metrics hold,
and retract the instant they don't. The flag is the lever; the evals are the gauge.
Shipping AI without both is betting the fleet on a vibe.""")

md("""## Recap

- **12-factor config**: read everything environment-specific from the environment; typed
  `Settings` (`pydantic-settings`) make it validated and **fail-fast** at startup.
- **Secrets** come from the environment / a secret manager (with rotation), never from
  code; commit a placeholder `.env.example`, gitignore the real `.env`.
- The **composition root** (`get_store` / `get_service`) is the one place that names a
  concrete adapter — so tests **override** a dependency by injection, no patching.
- A **percentage feature flag** with deterministic per-user bucketing ships a change
  *dark*, rolls it out by %, and rolls it **back instantly** — no redeploy.
- For AI features, pair flags with **online evals**: expand while metrics hold, retract
  the moment they don't.""")

md("""## Exercises

Use the empty cells below. (Solutions land in `solutions/` in Phase 2.)

1. **Required secret in prod mode.** Add a check: when `MOCK=0`, `Settings` must have a
   non-empty `anthropic_api_key`, raising a friendly error otherwise. 🔮 Predict the
   message a developer sees when they forget to set `APP_ANTHROPIC_API_KEY` with
   `COMPANION_MOCK=0`.
2. **Allowlist override.** Add `flags.force(name, user, on=True)` so specific users
   (your QA team) always get the new planner regardless of percentage. Predict how this
   interacts with a 0% rollout, then confirm.
3. **Monotonic rollout.** Show that ramping 10% → 25% → 50% only *adds* users to the new
   planner (no one flips back). Hint: compare the user sets at each step and check the
   subset relation. Why is that monotonicity a desirable property of a rollout?""")

code('# Exercise 1 -- your code here\n')
code('# Exercise 2 -- your code here\n')
code('# Exercise 3 -- your code here\n')

md("""## Next

You wired the service and learned to ship dark. Next: the small operability surface a
platform demands — health, graceful shutdown, multi-tenancy, and audit.

- ▶️ **Next notebook:** [`28-03-operational-contract-and-enterprise-must-haves.ipynb`](./28-03-operational-contract-and-enterprise-must-haves.ipynb)
  — liveness vs readiness, graceful drain, tenant scoping, and an append-only audit log.
- ◀️ **Previous:** [`28-01-hexagonal-ports-and-adapters.ipynb`](./28-01-hexagonal-ports-and-adapters.ipynb).
- 🧩 **Template:** the `Settings` + composition-root pattern feeds
  [`../../../templates/fastapi-agent-service/`](../../../templates/fastapi-agent-service/)
  and [`../../../templates/agent-project-starter/`](../../../templates/agent-project-starter/).
- 🔧 **Blueprint:**
  [`../../../blueprints/fastapi-agent-service/`](../../../blueprints/fastapi-agent-service/)
  — the `Depends`-based composition root in a real service.
- 🎓 **Capstone:** this is `capstone/app/config.py` (`Settings`) and the DI wiring;
  checkpoint `checkpoints/ch28-app-architecture`.
- 📖 **Book:** see §28.3 (Twelve-Factor + secrets), §28.4 (DI & composition root),
  §28.5 (feature flags / progressive delivery).""")


def to_source(text):
    lines = text.splitlines(keepends=True)
    return lines if lines else [""]


nb_cells = []
for ctype, text in cells:
    if ctype == "markdown":
        nb_cells.append({"cell_type": "markdown", "metadata": {}, "source": to_source(text)})
    else:
        nb_cells.append({"cell_type": "code", "execution_count": None, "metadata": {},
                         "outputs": [], "source": to_source(text)})

nb = {
    "cells": nb_cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUT.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", OUT)
