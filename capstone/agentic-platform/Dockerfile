# Multi-stage build for the agentic-platform.
#
#   Stage 1 (builder)  — installs dependencies into an isolated virtualenv.
#   Stage 2 (runtime)  — a slim image that copies ONLY that venv + the app code,
#                        runs as a non-root user, and ships a HEALTHCHECK.
#
# The api and the worker share THIS one image; docker-compose just runs a
# different command for each. Build once, run many (Ch 35).

ARG PYTHON_VERSION=3.12-slim-bookworm

# ---------------------------------------------------------------------------
# Stage 1 — builder: install dependencies into /opt/venv
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-only system deps (compilers/headers for psycopg, etc.). Kept out of the
# runtime image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Self-contained virtualenv we can copy wholesale into the runtime stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy only dependency metadata first so this layer is cached until deps change.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

# ---------------------------------------------------------------------------
# Stage 2 — runtime: slim, non-root, only what runs in production
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    COMPANION_MOCK=1

# Runtime-only system deps: libpq5 for psycopg, curl for the HEALTHCHECK.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Create an unprivileged user; never run the service as root.
RUN groupadd --system app && useradd --system --gid app --create-home app

# Bring in the prebuilt virtualenv from the builder stage.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy the modular-monolith source. .dockerignore keeps the build context lean.
# (These packages are built across the book's chapters; the api + worker share
# this same tree.)
COPY --chown=app:app app/ ./app/
COPY --chown=app:app agents/ ./agents/
COPY --chown=app:app rag/ ./rag/
COPY --chown=app:app memory/ ./memory/
COPY --chown=app:app prompts/ ./prompts/
COPY --chown=app:app llm/ ./llm/
COPY --chown=app:app security/ ./security/
COPY --chown=app:app workers/ ./workers/
COPY --chown=app:app mcp/ ./mcp/
COPY --chown=app:app evals/ ./evals/
COPY --chown=app:app observability/ ./observability/

USER app

# The port the api listens on (the worker ignores it).
ENV PORT=8000
EXPOSE 8000

# Liveness/readiness probe — hits the FastAPI /health endpoint. The worker (no
# HTTP server) disables this in compose.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail "http://localhost:${PORT}/health" || exit 1

# Default command runs the API. The worker service overrides this in compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
