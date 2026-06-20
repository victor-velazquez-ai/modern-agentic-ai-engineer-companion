# syntax=docker/dockerfile:1

# ---- Stage 1: builder -------------------------------------------------------
# Installs dependencies into an isolated virtualenv so the final image stays
# lean and contains no build toolchain.
# ▢ TODO: pin to a digest (python:3.12-slim@sha256:...) for reproducible builds.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Create the venv first so it is cached independently of the source.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only what pip needs to resolve dependencies, for better layer caching.
COPY pyproject.toml README.md ./
COPY app ./app

# Install the project (and its runtime deps) into the venv.
RUN pip install --upgrade pip && pip install .

# ---- Stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Run as a non-root user.
RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

# Bring in the built virtualenv and the application code.
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app ./app
COPY --chown=app:app pyproject.toml README.md ./

USER app

EXPOSE 8000

# Liveness/readiness: the orchestrator and `docker` both use this.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

# Serve with uvicorn. ▢ TODO: tune --workers for your CPU/latency profile.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
