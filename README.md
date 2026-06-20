# Modern Agentic AI Engineer — Official Companion

The hands-on companion to the book **_Modern Agentic AI Engineer: A Full Handbook — From
Zero to Senior / Architect-Level Engineer_** by Victor Velazquez.

The book teaches you *what* to build and *why*. This repository is where you **run it,
break it, and keep it** — a cell-by-cell learning lab, a shelf of professional blueprints,
a drawer of work-ready templates, and the complete reference capstone, all mapped chapter
by chapter to the book.

> **The book's promise still holds: you build the capstone yourself.** This repo doesn't
> replace that work — it *supports* it. Use the notebooks to understand each idea by
> running it, the blueprints to see a production-grade version, the templates to start your
> own projects faster, and the `capstone/` reference to check your work *after* you've built
> your own. Typing and building beats cloning and pasting — every time. See
> [`docs/HOW-TO-USE.md`](docs/HOW-TO-USE.md).

---

## 🚧 Status — planning skeleton (Phase 1)

This repo is being built in phases. **Right now it contains the complete plan, not the
finished notebooks.**

- ✅ **Phase 1 (now):** the full structure + a detailed `PLAN.md` in every chapter and asset
  folder describing exactly what will be built. This is the blueprint for the repo itself.
- ⏳ **Phase 2 (next):** implement the notebooks, blueprints, templates, and capstone — each
  one verified to run top-to-bottom.
- ⏳ **Phase 3:** ship the book's **2nd edition** (the master edition) that references this
  repo throughout. See [`docs/BOOK-INTEGRATION.md`](docs/BOOK-INTEGRATION.md).

If you're browsing and a folder only has a `PLAN.md` — that's expected for now. Watch the
[CHANGELOG](CHANGELOG.md) or star the repo to follow along.

---

## The four pillars

| Pillar | Folder | What it is | Use it to… |
|---|---|---|---|
| 📓 **Learn** | [`learn/`](learn/) | One folder per book chapter; Jupyter notebooks that teach the chapter's ideas **cell by cell** — theory you read *and run*. | Understand a concept by executing it, experimenting, and predicting outcomes. |
| 🧩 **Blueprints** | [`blueprints/`](blueprints/) | Self-contained, production-grade reference implementations of the recurring patterns (RAG pipeline, eval harness, MCP server, agent loop…). | Study a real, adaptable version of a pattern and lift it into your own systems. |
| 🛠️ **Templates** | [`templates/`](templates/) | Minimal, copy-me starting scaffolds (FastAPI agent service, agent project, ADR, eval dataset, CI pipeline, Terraform module…). | Start a new project *at work* in minutes with sane defaults baked in. |
| 🏗️ **Capstone** | [`capstone/`](capstone/) | The complete, runnable **agentic-platform** reference (the book's running project), plus per-Build **checkpoints**. | Build your own first — then compare against the reference and unblock yourself. |

---

## How it maps to the book

The book has **13 parts, 54 chapters, and 7 appendices**, all built around a single running
project: a general-purpose multi-agent platform. `learn/` mirrors that structure exactly:

```
learn/
  part-01-landscape-and-mindset/        # Ch 1–3
  part-02-software-engineering-foundations/  # Ch 4–7
  part-03-llm-substrate/                # Ch 8–11
  part-04-building-blocks-of-agents/    # Ch 12–15
  part-05-architectures-and-orchestration/   # Ch 16–20
  part-06-evaluation-observability-quality/  # Ch 21–23
  part-07-backend-apis-architecture/    # Ch 24–31
  part-08-cloud-and-infrastructure/     # Ch 32–36
  part-09-frontend-and-fullstack/       # Ch 37–38
  part-10-production-llmops/            # Ch 39–41
  part-11-architecting-at-scale/        # Ch 42–44
  part-12-specialized-frontiers/        # Ch 45–49
  part-13-career-and-leadership/        # Ch 50–54
  appendices/                          # A–G companion assets
```

Every chapter folder has a `PLAN.md` listing its planned notebooks, what each one teaches,
and which book sections (especially the 🔧 *Build* sections) it supports. The complete map
lives in [`docs/REPO-PLAN.md`](docs/REPO-PLAN.md).

---

## Quickstart (once Phase 2 lands)

```bash
git clone https://github.com/victor-velazquez-ai/modern-agentic-ai-engineer-companion.git
cd modern-agentic-ai-engineer-companion
cp .env.example .env          # add ANTHROPIC_API_KEY at minimum
python -m venv .venv && source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
jupyter lab                    # open learn/ and start with your chapter
```

Full environment setup (Python, Node, Docker, API keys, cost-free "mock" modes) is in
[`docs/SETUP.md`](docs/SETUP.md).

---

## Repository documentation

- [`docs/REPO-PLAN.md`](docs/REPO-PLAN.md) — the master plan: vision, full structure, the
  complete chapter→asset map, and the Phase 2 build process.
- [`docs/HOW-TO-USE.md`](docs/HOW-TO-USE.md) — the learner's guide: reading paths and how to
  use each pillar without falling into "paste, don't think."
- [`docs/SETUP.md`](docs/SETUP.md) — environment setup and running notebooks safely/cheaply.
- [`docs/NOTEBOOK-STANDARDS.md`](docs/NOTEBOOK-STANDARDS.md) — the authoring standard every
  notebook follows (so Phase 2 stays consistent and high quality).
- [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) — naming, the canonical `PLAN.md` template,
  and callout conventions mirrored from the book.
- [`docs/BOOK-INTEGRATION.md`](docs/BOOK-INTEGRATION.md) — how the 2nd edition references
  this repo, and the republish checklist.

---

## License

Code, templates, and configuration in this repository are released under the
[MIT License](LICENSE) so you can reuse them freely in your own and your employer's
projects. The teaching prose in notebooks accompanies the book *Modern Agentic AI Engineer*
and remains © 2026 Victor Velazquez; it's provided here for readers' personal learning. When
in doubt: **the code is yours to use; the lessons are yours to learn from.**

---

*Built as the companion I wish every technical book shipped with. — V.V.*
