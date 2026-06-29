# `core/` — config, errors, logging

The platform's cross-cutting foundations: the small set of things every other
module imports and that depend on nothing above them. First built in **Ch 4**
(§4 Build — the first real capstone code) and made twelve-factor in **Ch 28**.

> Reference, not a starting point. Build your own from the chapter's 🔧 Build
> section; consult this to compare. See the capstone [`README.md`](../../README.md).

## What's here

| File | Purpose | Chapter |
|---|---|---|
| `config.py` | `Settings` (Pydantic Settings) — one twelve-factor config object, loaded once, secrets from env only, **fail-fast** on a bad value. `get_settings()` is the accessor. | 4, 28 |
| `errors.py` | `AgenticError` hierarchy — typed failures (`NotFoundError`, `ValidationError`, `PermissionDeniedError`, `GuardrailError`, `ProviderError`, `RateLimitedError`) each with a stable `code` and HTTP `status` hint, so the API/worker layers map by type. | 4, 26 |
| `logging.py` | Structured (JSON) logging + a `request_id` bound per run via `contextvars`, so one run is greppable end to end. | 4, 23, 28 |

## The rules these encode

- **Config from the environment, never hard-coded** (twelve-factor). Secrets are
  read from env only — never constructor arguments, never logged. `Settings.redacted()`
  masks them so you can safely log the config shape.
- **Fail fast.** A missing/malformed required value raises `ConfigError` at
  startup, not on the first request. `Settings.require_provider_key()` enforces
  "live mode needs a key."
- **Mock by default.** `COMPANION_MOCK=1` (the repo convention) → the whole
  platform runs offline with zero keys. The model layer (`llm/`) reads this flag.
- **Typed errors.** Domain code raises `AgenticError` subclasses; it never imports
  a web framework. The HTTP layer reads `.status` / `.to_dict()`; the worker layer
  reads `ProviderError.retryable` to decide retry vs. fail-fast.

## Using it

```python
from core import get_settings, get_logger, bind_request_id

settings = get_settings()           # built once, cached
log = get_logger(__name__)

bind_request_id()                   # mint a run id (or pass an incoming one)
log.info("starting run", extra={"model": settings.default_model})
```

## Notes

- `config.py` uses **Pydantic Settings** when installed (the production path) and
  transparently falls back to a stdlib loader with the *same* public surface when
  it isn't — so importing the module never hard-fails on a missing dependency, and
  the mock path runs in a bare environment. Production always has Pydantic.
- These three modules have **no dependency on anything else in the platform** — by
  design. They are the bottom of the import graph.
