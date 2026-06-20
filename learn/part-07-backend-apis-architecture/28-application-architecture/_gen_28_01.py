"""Generator for 28-01-hexagonal-ports-and-adapters.ipynb. Not shipped; run once."""
import json
from pathlib import Path

OUT = Path(__file__).parent / "28-01-hexagonal-ports-and-adapters.ipynb"

cells = []


def md(text):
    cells.append(("markdown", text))


def code(text):
    cells.append(("code", text))


md("""# Isolate the Domain, Swap the Edge

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 28 §28.1–28.2 · type: walkthrough*  🔧 *This is the chapter's Build.*

Chapter 27 was architecture *in the large*. This notebook goes *inside* one service.
You'll structure a tiny domain service so its business logic depends on a **port** (a
`Protocol`), not on a concrete store — then **prove optionality** by swapping the
adapter underneath a fixed core, without changing a single line of the core file.
This is the exact shape the capstone's `app/` will take.""")

md("""## 🧠 Why this matters

Every long-lived service converges on one insight: **keep your business logic
independent of the things that change for external reasons** — the web framework, the
database, the model provider. Frameworks get replaced, vector stores get swapped, an
LLM vendor changes its API; your domain logic should not have to care.

The family of *layered*, *hexagonal* (ports-and-adapters), and *clean* architectures
all express this with the same rule: **the dependency rule** — dependencies point
*inward*, toward the domain. The web layer depends on the domain; the domain depends
on nothing external. The hexagon names the three regions: a pure **core**, the
**ports** it defines (interfaces it needs), and the **adapters** that implement those
ports for a specific technology.

The payoff is **testability and optionality**. Because the core depends on an
interface, you can test it with an in-memory fake — no network, no DB — and swap the
real adapter later with a one-line wiring change. In agentic systems, where you *will*
change vector stores and model providers more than once, that optionality is the
difference between a one-line swap and a painful rewrite.""")

md("""## Objectives & prerequisites

**By the end you can:**

- Define a **port** as a `typing.Protocol` and write a **pure domain service** that
  depends only on it (no framework or DB imports in the core).
- Provide a swappable **adapter** that satisfies the port *structurally* (no
  inheritance needed) and unit-test the service with an in-memory fake — offline.
- Swap in a *second* adapter and confirm the core is **byte-for-byte unchanged**.
- Apply **DDD-lite**: rename to the business's ubiquitous language and protect an
  aggregate's invariant behind a single entry point.

**Prereqs:** Ch 4 (typing, `Protocol`, async), Ch 27 (architecture styles, quality
attributes). No prior notebook in this chapter is required.

**Run first:** the Setup cell. This notebook is **fully offline by design** — it's a
structure lesson, not a model lesson — so there is nothing to bill and no key needed,
even with `MOCK=0`.""")

code('''# --- Setup -------------------------------------------------------------------
import asyncio
import hashlib
import os
import random
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from dotenv import load_dotenv

load_dotenv()  # never hardcode anything that differs between environments

# This notebook makes ZERO model/network calls: it teaches structure. The MOCK
# switch is here only for consistency with the rest of the companion. Whether it
# is 1 (default) or 0, the notebook runs free and offline -- there is no live path.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(28)  # determinism for anything stochastic (none here, but be principled)

print("Offline structure lab. No API key needed; nothing is billed in any mode.")''')

md("""## 1 · The port: what the core *needs*, not how it's done

A **port** is an interface the core declares for a capability it depends on. We use
`typing.Protocol`, so adapters satisfy it **structurally** — they just need methods of
the right shape, with no base class to inherit. That keeps the dependency arrow
pointing *into* the core: the adapter knows about the port, the port knows nothing
about the adapter.

`@runtime_checkable` lets us `isinstance`-check the shape in a teaching cell; in
production you'd usually lean on the static type checker instead.""")

code('''@runtime_checkable
class DocumentStore(Protocol):
    """Port: the only thing the domain knows about persistence/retrieval.

    The core depends on THIS, never on Postgres, Pinecone, Chroma, or httpx.
    """

    async def search(self, query: str, k: int) -> list[str]:
        ...


print("Port defined: DocumentStore.search(query, k) -> list[str]")''')

md("""## 2 · The core: a pure `ResearchService`

Here is the business logic. Notice what it **does not** import: no database driver, no
HTTP client, no framework. It accepts a `DocumentStore` in its constructor (that's
**dependency injection** — it's *given* its dependency rather than constructing one)
and uses only the port's `search` method. This file is the part you want to keep
stable for years.""")

code('''def _synthesize(question: str, passages: list[str]) -> str:
    """Pure, deterministic 'synthesis' so the lesson stays offline.

    A real service would call an LLM here; that call would itself sit behind a port
    (e.g. a ChatModel protocol) so the core never imports a model SDK directly.
    """
    if not passages:
        return f"No supporting passages found for: {question!r}"
    joined = " ".join(p.strip() for p in passages)
    return f"Q: {question}\\nA (grounded in {len(passages)} passages): {joined}"


class ResearchService:
    """Pure domain logic. Depends on the PORT, not on any concrete store."""

    def __init__(self, store: DocumentStore) -> None:
        self._store = store  # injected; the core never names a concrete adapter

    async def answer(self, question: str, k: int = 3) -> str:
        passages = await self._store.search(question, k=k)
        return _synthesize(question, passages)


# Capture the exact source of the core so we can PROVE it never changes (cell 6).
import inspect

CORE_SOURCE = inspect.getsource(ResearchService)
print("Core defined. ResearchService imports nothing external. Source length:",
      len(CORE_SOURCE), "chars")''')

md("""## 3 · Adapter #1: an in-memory fake — test with no network, no DB

The first adapter is a tiny in-memory store. Because `DocumentStore` is a `Protocol`,
this class **does not inherit** from anything — it just has a `search` method of the
right shape, so it satisfies the port structurally. That's all the core needs to run,
which means we can unit-test the service with **zero infrastructure**.""")

code('''@dataclass
class InMemoryStore:
    """Adapter: a dict-backed fake. Satisfies DocumentStore structurally."""

    docs: list[str] = field(default_factory=list)

    async def search(self, query: str, k: int) -> list[str]:
        # Trivial keyword match so results are deterministic and offline.
        terms = {t.lower() for t in query.split()}
        scored = [
            (sum(t in d.lower() for t in terms), d) for d in self.docs
        ]
        scored = [(s, d) for s, d in scored if s > 0]
        scored.sort(key=lambda sd: sd[0], reverse=True)
        return [d for _, d in scored[:k]]


# Three tiny in-memory "documents" -- no external services anywhere.
FIXTURE_DOCS = [
    "Refunds are issued within 30 days of purchase to the original payment method.",
    "The agent runtime caps each run at 12 steps to bound cost and latency.",
    "Vector search returns the top-k passages ranked by cosine similarity.",
]

# The whole point: the core is constructed with an ADAPTER, decided here at the edge.
fake = InMemoryStore(docs=FIXTURE_DOCS)
service = ResearchService(store=fake)

print("isinstance(fake, DocumentStore):", isinstance(fake, DocumentStore))
answer = asyncio.run(service.answer("how do refunds work?", k=1))
print(answer)''')

md("""## 4 · 🔮 Predict: swap in a second adapter — what in the core changes?

Below is a *second* adapter, `StubVectorStore` — pretend it's a Pinecone/Chroma client
(here it's offline and canned). We'll build the **same** `ResearchService` on top of it.

**Predict before running:**
1. How many lines of `ResearchService` (the core) must change to use the new adapter?
2. Where does the decision about *which* store to use actually live?""")

code('''@dataclass
class StubVectorStore:
    """Adapter #2: stands in for a real vector DB (Pinecone/Chroma).

    Offline + canned so the notebook never touches the network. The 'embedding' is a
    deterministic hash bucket -- enough to rank passages without a model.
    """

    docs: list[str] = field(default_factory=list)

    @staticmethod
    def _bucket(text: str) -> int:
        return int(hashlib.sha256(text.encode()).hexdigest(), 16) % 997

    async def search(self, query: str, k: int) -> list[str]:
        qb = self._bucket(query)
        ranked = sorted(self.docs, key=lambda d: abs(self._bucket(d) - qb))
        return ranked[:k]


# Build the SAME service class on a totally different adapter. The core is reused
# as-is: only this one wiring line names the new implementation.
vector = StubVectorStore(docs=FIXTURE_DOCS)
service_v2 = ResearchService(store=vector)  # <-- the entire "swap"

print(asyncio.run(service_v2.answer("step limit for an agent run", k=1)))''')

md("""## 5 · Confirm the core never moved

Optionality is only real if you can *prove* the core didn't change. We captured
`ResearchService`'s source before either swap. Compare it now: it's identical. Two
completely different storage technologies, **one unchanged core**.""")

code('''after_source = inspect.getsource(ResearchService)
print("Core source byte-for-byte unchanged across both adapters:",
      after_source == CORE_SOURCE)

# And the same logic produces grounded answers regardless of which adapter is behind
# the port -- the behavior the core guarantees is independent of the edge.
for name, svc in [("InMemoryStore", service), ("StubVectorStore", service_v2)]:
    print(f"[{name}]", asyncio.run(svc.answer("refund", k=1)))''')

md("""## 6 · DDD-lite: ubiquitous language + an aggregate that guards its invariant

Three Domain-Driven Design ideas pay for themselves immediately:

- **Ubiquitous language** — name things the way the business does, so "create a draft"
  in a meeting maps to `Draft` in code. Fewer translation bugs.
- **Bounded contexts** — a "user" in billing and a "user" in the agent runtime are
  different models; don't force one bloated shared class across the system.
- **Aggregates** — cluster the objects that must change together behind **one entry
  point** that enforces their rules, so an invariant can't be violated by reaching
  around it.

Below, a `Draft` aggregate enforces the rule *"a published draft must have non-empty
content and can't be edited again"* through its own methods — not via scattered
`if` checks in callers.""")

code('''class DraftError(Exception):
    """Raised when an operation would violate the Draft aggregate's invariants."""


@dataclass
class Draft:
    """Aggregate root for a research draft. All state changes go through its methods,
    so the invariant 'published drafts are non-empty and immutable' holds everywhere.
    """

    title: str
    body: str = ""
    status: str = "draft"  # 'draft' -> 'published'

    def edit(self, new_body: str) -> None:
        if self.status == "published":
            raise DraftError("cannot edit a published draft (it is immutable)")
        self.body = new_body

    def publish(self) -> None:
        if self.status == "published":
            raise DraftError("draft is already published")
        if not self.body.strip():
            raise DraftError("cannot publish an empty draft")
        self.status = "published"


d = Draft(title="Refund policy summary")
d.edit("Refunds within 30 days, original payment method.")
d.publish()
print("Published:", d.status, "| title:", d.title)

# Reaching around the entry point is impossible: the rule lives WITH the data.
try:
    d.edit("sneak in a change after publishing")
except DraftError as exc:
    print("Invariant held:", exc)''')

md("""## ⚠️ Pitfall: cargo-culting the full ceremony into a 200-line tool

Ports, adapters, four layers, and a DI container are **not free** — they add files and
indirection. A small, short-lived tool does not need all of it. Apply *as much* of
this structure as the service's **size and lifespan** justify; for a tiny script the
principle scales all the way down to "keep your business logic out of your route
handlers."

The cell below shows the over-engineered shape you should *not* reach for when the job
is small — a port, an adapter, and a factory wrapping what is really a one-liner.""")

code('''# OVER-ENGINEERED for the task (illustrative anti-pattern -- do NOT copy for small jobs):
@runtime_checkable
class GreeterPort(Protocol):
    def greet(self, name: str) -> str: ...


class EnglishGreeter:
    def greet(self, name: str) -> str:
        return f"Hello, {name}"


def make_greeter() -> GreeterPort:          # a "composition root" for... a greeting
    return EnglishGreeter()


print(make_greeter().greet("world"))

# The honest version of the same behavior, sized to the task:
def greet(name: str) -> str:
    return f"Hello, {name}"


print(greet("world"))
print("\\nRule of thumb: add a port the moment you have a SECOND plausible adapter or"
      "\\na real need to test the core in isolation -- not before.")''')

md("""## 🎯 Senior lens: the model is a *choice*, not a discovery

There is no single "correct" representation of a document, a draft, or a conversation
— only models that fit a context better or worse. The deepest DDD lesson is that
**boundaries are a design decision**, and senior engineers spend real effort choosing
ports and aggregates that match *how the business actually changes*.

Draw the boundary along the seam where change happens (storage tech, model provider,
billing vs. runtime), and a thousand future edits stay one-line swaps. Draw it in the
wrong place — couple the core to a vendor's response shape, or split one aggregate
across two services — and every change becomes a fight. The hexagon is a tool for
*aligning your code's seams with reality's seams*; that alignment, not the diagram, is
the value.""")

md("""## Recap

- The **dependency rule**: dependencies point inward. The core defines **ports**
  (interfaces it needs); **adapters** implement them at the edge.
- A `typing.Protocol` port lets adapters satisfy the interface **structurally** — no
  inheritance — so the core never imports a concrete store.
- **Optionality is testable**: we ran the same `ResearchService` on an in-memory fake
  and a stub vector store with the core **byte-for-byte unchanged**.
- **DDD-lite**: ubiquitous language reduces translation bugs; an **aggregate** guards
  its invariant behind one entry point so callers can't reach around the rule.
- **Restraint**: apply only as much structure as size and lifespan justify; add a port
  when a second adapter or isolated test actually appears.""")

md("""## Exercises

Use the empty cells below. (Solutions land in `solutions/` in Phase 2.)

1. **A third adapter.** Write `FileStore` whose `search` reads passages from
   `data/passages.txt` (one per line) and keyword-matches them. Build
   `ResearchService(FileStore(...))` and confirm the core source is *still* unchanged.
   🔮 Predict: which existing cell, if any, needs editing besides the wiring line?
2. **Tighten the aggregate.** Add a `withdraw()` method to `Draft` that's only legal
   from `draft` status, and a `MAX_TITLE = 80` invariant enforced in `__post_init__`.
   Predict the exact `DraftError` for a 100-char title, then confirm.
3. **Find the leak.** Add an `import sqlalchemy` *inside* `ResearchService.answer` and
   argue (in a markdown cell) why that single line breaks the dependency rule and what
   it costs you in testing — then remove it.""")

code('# Exercise 1 -- your code here\n')
code('# Exercise 2 -- your code here\n')
code('# Exercise 3 -- your code here\n')

md("""## Next

You isolated the domain and swapped the edge. Next: wire it from the environment, at
one composition root, and ship a change *dark*.

- ▶️ **Next notebook:** [`28-02-config-di-and-feature-flags.ipynb`](./28-02-config-di-and-feature-flags.ipynb)
  — 12-factor `Settings`, the composition root, and feature flags / progressive
  delivery.
- 🧩 **Template (the real layout):**
  [`../../../templates/fastapi-agent-service/`](../../../templates/fastapi-agent-service/)
  — the hexagonal `core/` + adapters this notebook prototypes, plus
  [`../../../templates/agent-project-starter/`](../../../templates/agent-project-starter/).
- 🔧 **Blueprint:** these patterns underpin
  [`../../../blueprints/fastapi-agent-service/`](../../../blueprints/fastapi-agent-service/).
- 🎓 **Capstone:** this defines the shape of `capstone/app/` (`core/` domain, ports &
  adapters); checkpoint `checkpoints/ch28-app-architecture`.
- 📖 **Book:** see §28.1 (the dependency rule) and §28.2 (DDD-lite).""")


def to_source(text):
    lines = text.splitlines(keepends=True)
    return lines if lines else [""]


nb_cells = []
for ctype, text in cells:
    if ctype == "markdown":
        nb_cells.append({
            "cell_type": "markdown",
            "metadata": {},
            "source": to_source(text),
        })
    else:
        nb_cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": to_source(text),
        })

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
