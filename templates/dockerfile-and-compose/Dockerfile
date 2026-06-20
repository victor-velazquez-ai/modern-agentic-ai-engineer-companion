# Multi-stage build for a Python agent service.
#
#   Stage 1 (builder)  — installs dependencies into an isolated virtualenv.
#   Stage 2 (runtime)  — a slim image that copies ONLY that venv + the app code,
#                        runs as a non-root user, and ships a HEALTHCHECK.
#
# The api and the worker share THIS one image; compose just runs a different
# command for each (see docker-compose.yml). Build once, run many.
#
# ▢ TODO: this expects your application package to be copied in below and an
#   ASGI app importable as `app.main:app` (matches ../fastapi-agent-service/).
#   Adjust the COPY paths, the dependency file, and the CMD to match your project.

# Pin the base image (digest-pinning is even stronger; tag is a sane default).
ARG PYTHON_VERSION=3.12-slim-bookworm

# ---------------------------------------------------------------------------
# Stage 1 — builder: compile/install dependencies into /opt/venv
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS builder

# Faster, quieter, reproducible Python in containers.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-only system deps (compilers/headers). Kept out of the runtime image.
# ▢ TODO: add any -dev libraries your wheels need to compile (e.g. libpq-dev).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Self-contained virtualenv we can copy wholesale into the runtime stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy only dependency metadata first so this layer is cached until deps change.
# ▢ TODO: point these at YOUR dependency files. Keep one of the two blocks.
#   - pyproject (recommended; matches the other templates):
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .
#   - or a plain requirements.txt instead of the two lines above:
# COPY requirements.txt ./
# RUN pip install --upgrade pip && pip install -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2 — runtime: slim, non-root, only what runs in production
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Runtime-only system deps. curl is used by the HEALTHCHECK below.
# ▢ TODO: add runtime libs your app needs (e.g. libpq5 for postgres).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create an unprivileged user; never run the service as root.
RUN groupadd --system app && useradd --system --gid app --create-home app

# Bring in the prebuilt virtualenv from the builder stage.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy the application source. .dockerignore keeps the context lean.
# ▢ TODO: copy YOUR package(s) here (this matches ../fastapi-agent-service/).
COPY --chown=app:app app/ ./app/

USER app

# The port the api listens on (the worker ignores it). Documentation + default.
ENV PORT=8000
EXPOSE 8000

# Liveness/readiness probe — hits the FastAPI /health endpoint.
# For the worker (no HTTP server) override or disable this in compose.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail "http://localhost:${PORT}/health" || exit 1

# Default command runs the API. The worker service overrides this in compose.
# ▢ TODO: match your ASGI app path / process manager.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
