# Setup

Mirrors the book's Appendix A, but living and tested. The goal: get to a running notebook in
a few minutes, and stay cost-free until you choose otherwise.

> Phase 1 note: the toolchain below is what the **notebooks will need in Phase 2**. Right now
> the repo holds plans, so you don't need any of this to *read* it.

---

## Prerequisites

- **Python 3.12+**
- **Node.js 20+** (only for the frontend chapters, Part IX, and the capstone `web/`)
- **Docker** (only for chapters that run Postgres/Redis/Chroma locally, and the capstone)
- A **model API key** (Anthropic recommended; the book's stack is Anthropic-first) — *only*
  when you switch a notebook to live mode.

---

## Python environment

```bash
git clone https://github.com/victor-velazquez-ai/modern-agentic-ai-engineer-companion.git
cd modern-agentic-ai-engineer-companion

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
jupyter lab
```

Open `learn/`, find your chapter folder, and start with its lowest-numbered notebook.

---

## Environment variables

```bash
cp .env.example .env
```

Then edit `.env`. **You need nothing to run in mock mode.** For live model output, set at
minimum `ANTHROPIC_API_KEY` and `COMPANION_MOCK=0`. Every variable is documented in
[`.env.example`](../.env.example).

---

## Mock mode (cost-free, default)

Notebooks read a single switch:

```python
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"
```

- `COMPANION_MOCK=1` (default) — model calls return realistic **canned** responses. Notebooks
  run free, offline, and deterministically. Perfect for first reads and CI.
- `COMPANION_MOCK=0` — calls hit the live API. The notebook's setup cell prints an estimated
  **token cost** so there are no surprises.

---

## Optional services (only some chapters)

A `docker-compose.yml` (Phase 2) brings up Postgres+pgvector, Redis, and Chroma for the data,
memory, RAG, and Celery chapters and the capstone:

```bash
docker compose up -d postgres redis chroma
```

Chapters that need a service say so in their first cell and degrade gracefully (or mock) when
it's absent.

---

## Troubleshooting

- **Notebook won't import a package** → ensure the venv is active and `pip install -r
  requirements.txt` ran; a notebook needing extras declares them in its first cell.
- **Live mode errors** → check the key in `.env` and that `COMPANION_MOCK=0`; mock mode never
  needs a key.
- **Service connection refused** → start the compose services above, or run the notebook in
  its mock path.
