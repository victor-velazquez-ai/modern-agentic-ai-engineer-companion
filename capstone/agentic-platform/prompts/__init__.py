"""Versioned prompt registry (Ch 10) — prompts as tracked artifacts.

The platform keeps prompts as **versioned templates on disk**, loaded through a
small registry, so a prompt is a reviewable, diffable, pinnable artifact — not a
string buried in an f-string somewhere. This is the foundation for the "pin a
prompt + tool + model triple" discipline Ch 44 formalizes.

Public API (see :mod:`prompts.registry`):

* ``load(name, version="latest", *, variables=None)`` → a :class:`RenderedPrompt`
  (system text + message list + the model/params recorded in ``meta.yaml``).
* ``render(template, variables)`` — fill ``{{placeholders}}`` in one template.
* ``list_versions(name)`` / ``available_prompts()`` — discovery.

Layout (one directory per prompt)::

    prompts/
      <name>/
        meta.yaml      # name, owner, description, latest pointer, model + params
        v1/ {system.md, user.md}
        v2/ ...

This module reads files and substitutes variables — no business logic, no network
calls, no secrets. Example variable values in prompt files are placeholders.
"""

from __future__ import annotations

from .registry import (
    MissingVariableError,
    PromptError,
    PromptNotFoundError,
    RenderedPrompt,
    UnknownVariableError,
    available_prompts,
    list_versions,
    load,
    render,
    resolve_version,
)

__all__ = [
    "load",
    "render",
    "resolve_version",
    "list_versions",
    "available_prompts",
    "RenderedPrompt",
    "PromptError",
    "PromptNotFoundError",
    "MissingVariableError",
    "UnknownVariableError",
]
