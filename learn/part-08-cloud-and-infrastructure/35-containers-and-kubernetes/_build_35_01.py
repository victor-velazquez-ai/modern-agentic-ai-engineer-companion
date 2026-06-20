"""Builder for 35-01-dockerize-a-service.ipynb (temporary; not part of the deliverable)."""
import json
import io

cells = []


def md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": _split(text)})


def code(text):
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _split(text),
    })


def _split(text):
    text = text.strip("\n")
    lines = text.split("\n")
    return [ln + "\n" for ln in lines[:-1]] + [lines[-1]]


# 1. Title + header
md(r"""# 🔧 Build: Dockerize the capstone API

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 35 §35.1 · type: walkthrough*

**The promise:** you will turn the capstone's FastAPI agent service into a small, layered, **non-root**, multi-stage image and run it with `docker compose` — the build artifact every cloud deploy in Part VIII consumes.""")

# 2. Why this matters
md(r"""## 🧠 Why this matters

A container image is your application *plus its world* — code, Python runtime, libraries, system deps — frozen into one portable thing that runs identically on your laptop, in CI, and in production. The book's framing: *"it works on my machine — so we'll ship your machine."*

For AI services this reproducibility is worth real money. Agent stacks drag in thorny dependency trees (a specific Python, native build tools, CUDA, model libraries), and "works locally, breaks in the cluster" is the default failure mode. The Dockerfile is the **contract** that pins all of it. Get the image small, layered for cache, and non-root, and the same artifact flows unchanged into Fargate/ECR (Ch 33) or Kubernetes (§35.2) — you build it once, here, offline, for free.""")

# 3. Objectives + prereqs
md(r"""## Objectives & prereqs

**By the end you can:**
- Author a **multi-stage** Dockerfile (build stage installs deps; slim runtime copies only artifacts) in the §35.1 shape — non-root `USER`, explicit `CMD`.
- Order layers so a code change does **not** bust the dependency-install cache.
- Wire a minimal `docker-compose.yml` (API + Postgres + Redis) for local dev, run it, hit the health endpoint, and tear down cleanly.
- Spot the three classic image smells — root user, fat base, baked-in secrets — and fix each.

**Prereqs:** Ch 25 (the FastAPI service we containerize). Docker installed locally is the *one real* local dependency; if it's absent, every "run" cell **degrades to printing the exact command** so the notebook still completes.

**Runs free & offline.** No cloud, no API key, no spend — this notebook only writes files into a temp dir and (optionally) shells out to your *local* Docker.""")

# 4. Setup
code(r'''# Setup — imports, env, the MOCK switch, and a Docker probe.
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# MOCK=1 (default) keeps this notebook free, offline, and deterministic: we never
# build/run real containers — we author the files and print the commands instead.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

# Is a real Docker CLI available? Even with MOCK=1 we only ever *describe* commands;
# this probe just lets the prose be honest about your machine.
DOCKER = shutil.which("docker") is not None

# A scratch build context so we never touch the repo tree.
BUILD = Path("_build_context")
BUILD.mkdir(exist_ok=True)

print("MOCK mode :", MOCK, "— offline; files written, commands printed (not executed)"
      if MOCK else "— LIVE; cells may invoke your local Docker")
print("docker CLI:", "found" if DOCKER else "not found — run cells degrade to printed commands")
print("context   :", BUILD.resolve())''')

# 5. Body
md(r"""## The thing we're shipping: a minimal FastAPI agent service

The capstone exposes an agent over HTTP with FastAPI (Ch 25). We don't need the whole app to learn the *containerization* — a faithful stub with a `/healthz` endpoint is enough, and it matches the service shape the real one uses. We write it into the scratch context.""")

code(r'''# A faithful, tiny stand-in for the capstone's FastAPI service (the shape from Ch 25).
# Built from a list of lines so there are no nested triple-quotes to trip on.
APP = "\n".join([
    "import os",
    "",
    "from fastapi import FastAPI",
    "",
    'app = FastAPI(title="agent-service")',
    "",
    "",
    '@app.get("/healthz")',
    "def healthz():",
    "    # Liveness/readiness target (Ch 28). Cheap, dependency-free, always-on.",
    '    return {"status": "ok", "service": "agent-service"}',
    "",
    "",
    '@app.get("/")',
    "def root():",
    "    # Secrets come from the ENVIRONMENT at runtime — never baked into the image.",
    '    model = os.environ.get("MODEL", "claude-opus-4-8")',
    '    return {"agent": "ready", "model": model}',
    "",
])

(BUILD / "main.py").write_text(APP, encoding="utf-8")

# A deliberately small runtime requirement set for the demo image.
REQS = "fastapi\nuvicorn[standard]\n"
(BUILD / "requirements.txt").write_text(REQS, encoding="utf-8")

print("wrote:", *(p.name for p in BUILD.iterdir()))
print("\n--- main.py ---")
print(APP)''')

md(r"""### Author the multi-stage Dockerfile (the §35.1 shape)

A good image is **small**, **layered for cache**, and runs as a **non-root** user. A *multi-stage* build gets you all three: a `build` stage compiles/installs dependencies with the full toolchain, then a slim runtime stage copies only the installed artifacts — the build tools never ship.

This is the exact shape from §35.1, lightly annotated.""")

code(r'''DOCKERFILE = textwrap.dedent("""
    # --- build stage: full toolchain, installs deps into a relocatable prefix ---
    FROM python:3.12-slim AS build
    WORKDIR /app
    COPY requirements.txt .
    RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

    # --- runtime stage: slim, no build tools shipped ---
    FROM python:3.12-slim
    COPY --from=build /install /usr/local      # only the installed artifacts cross over
    COPY . /app
    WORKDIR /app
    USER 1000                                  # never run as root
    EXPOSE 8000
    CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
""").lstrip()

(BUILD / "Dockerfile").write_text(DOCKERFILE, encoding="utf-8")
print(DOCKERFILE)''')

md(r"""Two details earn their keep:

- `--prefix=/install` makes the installed packages **relocatable**, so `COPY --from=build /install /usr/local` drops them into the slim runtime without dragging `pip`, compilers, or caches along.
- `USER 1000` switches off root *before* `CMD`. A numeric UID (not a named user) is the portable choice — it needs no `useradd` and behaves the same on any base.""")

md(r"""### 🔮 Predict: which line, when changed, busts the dependency cache?

Docker caches each layer and reuses it until something in that layer (or above it) changes. Layers are evaluated **top to bottom**: change a line and *every layer below it* is rebuilt.

Look at this (deliberately mis-ordered) build stage, where the whole project is copied **before** dependencies are installed:

```dockerfile
FROM python:3.12-slim AS build
WORKDIR /app
COPY . .                                  # <-- copies ALL source, including main.py
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
```

**Predict:** you edit one line of `main.py` (your app code) and rebuild. Does `pip install` — the slow layer — run again, or is it served from cache?""")

code(r'''# Model Docker's layer cache as a simple top-to-bottom invalidation walk.
def rebuild(layers, changed_files):
    """Given ordered (name, inputs) layers and a set of edited files, return which
    layers must rebuild. Once a layer's inputs change, it and everything below rebuild."""
    invalidated = False
    plan = []
    for name, inputs in layers:
        if invalidated or (set(inputs) & changed_files):
            invalidated = True
            plan.append((name, "REBUILD"))
        else:
            plan.append((name, "cached"))
    return plan


# BAD order: `COPY . .` (depends on every file) sits ABOVE the pip install.
bad = [
    ("FROM python:3.12-slim", []),
    ("COPY . .", ["main.py", "requirements.txt"]),
    ("RUN pip install ...", ["requirements.txt"]),
]

for name, status in rebuild(bad, changed_files={"main.py"}):
    print(f"  {status:8} {name}")''')

md(r"""**What you just saw.** Editing `main.py` invalidates `COPY . .`, and because `pip install` sits *below* it, the slow install layer rebuilds too — every single code edit re-downloads your whole dependency tree. The fix is to copy only `requirements.txt`, install, *then* copy the rest of the source.""")

code(r'''# GOOD order: copy + install deps FIRST, copy app code LAST.
good = [
    ("FROM python:3.12-slim", []),
    ("COPY requirements.txt .", ["requirements.txt"]),
    ("RUN pip install ...", ["requirements.txt"]),
    ("COPY . .", ["main.py", "requirements.txt"]),
]

print("Edit main.py only:")
for name, status in rebuild(good, changed_files={"main.py"}):
    print(f"  {status:8} {name}")

print("\nEdit requirements.txt:")
for name, status in rebuild(good, changed_files={"requirements.txt"}):
    print(f"  {status:8} {name}")

# The payoff, asserted: a pure code edit must NOT rebuild the pip layer.
plan = dict(rebuild(good, changed_files={"main.py"}))
assert plan["RUN pip install ..."] == "cached", "code edits must not bust the dep cache"
print("\nPASS — a code-only edit reuses the cached dependency install.")''')

md(r"""Our real Dockerfile already copies `requirements.txt` and installs **before** `COPY . /app`, so it has the good ordering. The lesson generalizes: **put your least-frequently-changing inputs in the lowest (earliest) layers.**""")

md(r"""### Compose: the API + Postgres + Redis for local dev

A single container is rarely the whole local story — the agent service talks to Postgres (state) and Redis (cache/queue, Ch 31). `docker compose` declares all three and the network between them in one file. Note where secrets and config live: in the **environment at runtime**, never in the image.""")

code(r'''COMPOSE = textwrap.dedent("""
    services:
      api:
        build: .
        ports:
          - "8000:8000"
        environment:
          # Secrets/config injected at RUNTIME from your shell/.env — not baked in.
          - MODEL=${MODEL:-claude-opus-4-8}
          - DATABASE_URL=postgresql://app:app@db:5432/app
          - REDIS_URL=redis://cache:6379/0
        depends_on:
          - db
          - cache
      db:
        image: postgres:16-alpine
        environment:
          - POSTGRES_USER=app
          - POSTGRES_PASSWORD=app      # local-dev only; real creds come from a secret store
          - POSTGRES_DB=app
      cache:
        image: redis:7-alpine
""").lstrip()

(BUILD / "docker-compose.yml").write_text(COMPOSE, encoding="utf-8")
print(COMPOSE)''')

md(r"""### Build, run, probe, tear down

Here is the full local loop. In `MOCK=1` (the default) these cells **print** the exact commands rather than execute them, so the notebook stays free and offline — and they print identically when Docker isn't installed. Flip `COMPANION_MOCK=0` *and* have Docker running to actually build and serve.""")

code(r'''def run_or_show(cmd, cwd=BUILD):
    """Execute a shell command on the LIVE path; otherwise print it verbatim.
    Degrades to printing whenever MOCK=1 OR Docker is missing — so it always 'completes'."""
    printed = "$ " + " ".join(cmd)
    if MOCK or not DOCKER:
        print(printed, "   # (printed, not executed)")
        return None
    print(printed)
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)


# Build the image and inspect its size (smaller = faster pulls, cheaper deploys).
run_or_show(["docker", "build", "-t", "agent-service:dev", "."])
run_or_show(["docker", "images", "agent-service:dev",
             "--format", "{{.Repository}}:{{.Tag}}  {{.Size}}"])''')

code(r'''# Bring the whole local stack up in the background, then probe the health endpoint.
run_or_show(["docker", "compose", "up", "-d", "--build"])
run_or_show(["docker", "compose", "exec", "api",
             "python", "-c", "import urllib.request,sys;"
             "print(urllib.request.urlopen('http://localhost:8000/healthz').read())"])

# In MOCK mode, show the realistic, canned response so you know what 'healthy' looks like.
if MOCK or not DOCKER:
    print("\n# expected /healthz body:")
    print('  {"status":"ok","service":"agent-service"}')''')

code(r'''# Read recent logs (read the boot line + the request), then tear DOWN cleanly.
run_or_show(["docker", "compose", "logs", "--tail", "5", "api"])
run_or_show(["docker", "compose", "down", "-v"])   # -v removes the throwaway db/cache volumes

if MOCK or not DOCKER:
    print("\n# expected api log tail (uvicorn):")
    print('  INFO:     Uvicorn running on http://0.0.0.0:8000')
    print('  INFO:     127.0.0.1 - "GET /healthz HTTP/1.1" 200 OK')''')

md(r"""### ⚠️ Pitfall: root user, fat base, and secrets baked into layers

Three image smells cause most production grief. Each has a one-line fix — and the "secret in a layer" one is the dangerous one, because the secret survives in image history even if a later layer deletes it.""")

code(r'''# The three smells, each shown then fixed.
smells = [
    ("Runs as root",
     "FROM python:3.12       # full image, root by default",
     "FROM python:3.12-slim  # + USER 1000 before CMD"),
    ("Fat base image",
     "FROM python:3.12       # ~1 GB, ships compilers & headers",
     "FROM python:3.12-slim  # ~150 MB; multi-stage drops build tools"),
    ("Secret baked into a layer",
     'ENV ANTHROPIC_API_KEY=sk-ant-...   # frozen into image history forever',
     "# inject at RUNTIME: compose `environment:` / `docker run -e` / a secret store"),
]

for title, bad, fix in smells:
    print(f"⚠️  {title}")
    print(f"    bad : {bad}")
    print(f"    fix : {fix}\n")

# Why 'delete it in a later layer' does NOT work for a baked secret:
def secret_in_history(layers):
    """An ENV/ARG secret persists in EVERY later image layer's history, even if 'removed'."""
    return any("ANTHROPIC_API_KEY" in ly for ly in layers)

leaky = ["FROM python:3.12-slim",
         "ENV ANTHROPIC_API_KEY=sk-ant-xxx",   # leak introduced here...
         "RUN unset ANTHROPIC_API_KEY"]         # ...this does NOT scrub history
assert secret_in_history(leaky), "the key is still recoverable from image history"
print("Lesson: a baked secret is recoverable from history — keep it OUT of the build entirely.")''')

md(r"""### ⚠️ Pitfall (GPU, §35.1): CUDA base image must match the host driver

This one we *explain* rather than run, to keep the notebook GPU-free. For GPU workloads your base image's CUDA version must line up with the **host's driver**, and you run with the **NVIDIA container runtime** so the container can see the GPU. Version drift here is the single most common "works locally, fails in the cluster" trap.

```dockerfile
# GPU serving (illustrative — NOT executed here):
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04   # pin CUDA in LOCKSTEP with cluster drivers
# ... and run with:  docker run --gpus all ...   (needs the NVIDIA Container Toolkit)
```

Pin the CUDA base deliberately and keep it in lockstep with the cluster's drivers — treat a driver bump as a deploy event, not a surprise.""")

# 6. Senior lens
md(r"""## 🎯 Senior lens

A small, reproducible image is the **unit of deploy**, and it's the same unit everywhere: Fargate pulls it from ECR (Ch 33), Kubernetes schedules it as a Pod (§35.2), your teammate runs it with one `compose up`. That portability is exactly why the discipline here pays off downstream — the Dockerfile is the contract that lets you defer the *where* (managed containers vs. K8s) without re-engineering the *what*.

So a senior spends the effort to get the image right **once**: multi-stage to stay slim, deps-before-code layering to keep CI fast and cheap, non-root and no baked secrets for security. Cheap to do here; expensive to retrofit once five deploy paths depend on it.""")

# 7. Recap
md(r"""## Recap

- An **image = code + runtime + deps frozen** — "ship your machine," reproducible from laptop to cluster.
- **Multi-stage** keeps the runtime slim: build with the full toolchain, copy only the installed artifacts into a slim base.
- **Layer order is cache:** copy + install `requirements.txt` *before* the app source, so a code edit doesn't rebuild your dependency tree.
- **Compose** declares the local stack (API + Postgres + Redis); secrets/config come from the **environment at runtime**, never baked into a layer.
- The three smells — **root user, fat base, baked secrets** — each have a one-line fix; a baked secret survives in image history, so keep it out of the build entirely.
- **GPU:** pin the CUDA base in lockstep with the host driver and use the NVIDIA runtime — the #1 local-vs-cluster trap.""")

# 8. Exercises
md(r"""## Exercises

Each *changes something* and asks you to predict first.

1. **Add a `.dockerignore`.** Write one that excludes `_build_context` clutter (`__pycache__`, `.env`, `*.pyc`, `.git`). Predict how it affects `COPY . /app` and the final image size, then list what *must never* be copied in.
2. **Pin for reproducibility.** Change `requirements.txt` to pin exact versions (`fastapi==…`, `uvicorn==…`). Predict which rebuilds: the `pip install` layer, the `COPY . /app` layer, or both — then reason it out against the cache rule.
3. **Make the runtime fail fast.** Add a `HEALTHCHECK` instruction that curls `/healthz`. Predict what `docker ps` shows for the container's STATUS before vs. after the app is ready, and how that ties to Ch 28 readiness probes.""")

code(r'''# Exercise 1 — your .dockerignore here (write it into BUILD and re-inspect).
''')

code(r'''# Exercise 2 — pin versions in requirements.txt; reason about which layers rebuild.
''')

code(r'''# Exercise 3 — add a HEALTHCHECK to the Dockerfile; predict the STATUS transitions.
''')

# 9. Next
md(r"""## Next

- **Next notebook:** [`35-02-kubernetes-without-a-cluster.ipynb`](35-02-kubernetes-without-a-cluster.ipynb) — read real K8s manifests and simulate desired-state reconciliation + HPA scaling, fully offline.
- **Template this produces:** [`templates/dockerfile-and-compose/`](../../../templates/dockerfile-and-compose/) — this build, hardened into a copy-into-your-job scaffold (the production version of what you just wrote).
- **Book:** §35.1 (Docker for AI services — multi-stage, non-root, slim runtime).
- **Capstone:** the image you built here is what `capstone/app/` and `capstone/workers/` ship as — it advances checkpoint `checkpoints/ch35-containerized`. Ch 36 (Infrastructure as Code) then deploys this image.""")

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = (Path(__file__).parent / "35-01-dockerize-a-service.ipynb")
with io.open(out, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print("wrote", out, "with", len(cells), "cells")
