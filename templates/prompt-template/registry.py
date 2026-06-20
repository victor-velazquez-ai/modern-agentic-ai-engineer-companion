"""Versioned prompt registry.

Loads a *named, versioned* prompt from the ``prompts/`` directory and renders it
into the message list you pass straight to the Claude Messages API. Prompts live
in files (Markdown), not in inline f-strings, so they diff cleanly, review well,
and can be pinned/rolled back like any other code.

Layout this loader expects (one directory per prompt)::

    prompts/
      <name>/
        meta.yaml          # name, owner, description, latest, model, params
        v1/
          system.md        # system template — {{variables}} as placeholders
          user.md          # user template — {{variables}}
        v2/
          system.md
          user.md

Public API
----------
``load(name, version="latest", *, variables=None)``
    Resolve a prompt to a rendered ``RenderedPrompt`` (system text + message
    list + the model/params recorded in ``meta.yaml``).
``render(template, variables)``
    Fill ``{{placeholders}}`` in a single template string. Raises on any
    unknown or missing variable — no silent missing-var bugs.
``list_versions(name)``
    The available ``vN`` version ids for a prompt, sorted numerically.
``available_prompts()``
    Every prompt name discoverable under ``prompts/``.

This module has **no business logic and no network calls** — it only reads files
and substitutes variables. There are no secrets here; example variable values in
the prompt files are placeholders, never real customer data.

NOTE: requires PyYAML (``pip install pyyaml``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# The prompts/ directory lives next to this file. If you copy registry.py to a
# different location than its prompts/ dir, override PROMPTS_DIR here.
# TODO: point this at your repo's prompts directory if you move registry.py.
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Matches {{ variable_name }} with optional surrounding whitespace.
_PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")

# HTML comments (<!-- ... -->) are author notes — stripped from templates before
# rendering so guidance/TODOs never reach the model and don't get mis-parsed as
# placeholders.
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


class PromptError(Exception):
    """Base class for every error this module raises."""


class PromptNotFoundError(PromptError):
    """The named prompt or the requested version does not exist on disk."""


class MissingVariableError(PromptError):
    """A template referenced a ``{{variable}}`` that was not supplied."""


class UnknownVariableError(PromptError):
    """A variable was supplied that the template never references.

    This is treated as an error on purpose: an unused variable almost always
    means a typo or a stale call site, and silently dropping it hides bugs.
    """


@dataclass(frozen=True)
class RenderedPrompt:
    """The result of :func:`load` — ready to hand to the Messages API.

    ``messages`` is the ``messages=[...]`` argument. ``system`` is the
    top-level ``system=`` string (empty if the prompt has no system template).
    ``model`` and ``params`` come from ``meta.yaml`` so the call site uses the
    exact model + sampling settings this prompt version was tuned for.
    """

    name: str
    version: str
    system: str
    messages: list[dict[str, str]]
    model: str
    params: dict[str, Any] = field(default_factory=dict)


def render(template: str, variables: dict[str, Any]) -> str:
    """Fill ``{{placeholders}}`` in ``template`` from ``variables``.

    Raises :class:`MissingVariableError` if the template references a variable
    that is absent, and :class:`UnknownVariableError` if ``variables`` contains
    a key the template never uses. Both failures are loud by design.
    """
    referenced = set(_PLACEHOLDER_RE.findall(template))
    supplied = set(variables)

    missing = referenced - supplied
    if missing:
        raise MissingVariableError(
            "Missing variable(s) for template: " + ", ".join(sorted(missing))
        )

    unknown = supplied - referenced
    if unknown:
        raise UnknownVariableError(
            "Unknown variable(s) not used by template: " + ", ".join(sorted(unknown))
        )

    def _sub(match: re.Match[str]) -> str:
        return str(variables[match.group(1)])

    return _PLACEHOLDER_RE.sub(_sub, template)


def _prompt_dir(name: str) -> Path:
    directory = PROMPTS_DIR / name
    if not directory.is_dir():
        raise PromptNotFoundError(f"No prompt named {name!r} under {PROMPTS_DIR}")
    return directory


def _load_meta(name: str) -> dict[str, Any]:
    meta_path = _prompt_dir(name) / "meta.yaml"
    if not meta_path.is_file():
        raise PromptNotFoundError(f"Prompt {name!r} has no meta.yaml")
    data = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise PromptError(f"meta.yaml for {name!r} must be a mapping")
    return data


def _version_key(version: str) -> int:
    # "v2" -> 2, for numeric sorting. Non-conforming dirs sort last.
    match = re.fullmatch(r"v(\d+)", version)
    return int(match.group(1)) if match else -1


def available_prompts() -> list[str]:
    """Return every prompt name discoverable under ``prompts/``."""
    if not PROMPTS_DIR.is_dir():
        return []
    return sorted(
        p.name
        for p in PROMPTS_DIR.iterdir()
        if p.is_dir() and (p / "meta.yaml").is_file()
    )


def list_versions(name: str) -> list[str]:
    """Return the available ``vN`` version ids for ``name``, sorted ascending."""
    directory = _prompt_dir(name)
    versions = [
        p.name
        for p in directory.iterdir()
        if p.is_dir() and re.fullmatch(r"v\d+", p.name)
    ]
    return sorted(versions, key=_version_key)


def resolve_version(name: str, version: str = "latest") -> str:
    """Resolve ``"latest"`` to a concrete ``vN`` using ``meta.yaml``.

    Passing a concrete version (e.g. ``"v1"``) returns it unchanged after
    checking it exists. ``"latest"`` reads the ``latest`` pointer in
    ``meta.yaml`` so resolution is deterministic and reviewable — it is not
    "whatever sorts highest on disk".
    """
    versions = list_versions(name)
    if not versions:
        raise PromptNotFoundError(f"Prompt {name!r} has no vN/ version directories")

    if version == "latest":
        meta = _load_meta(name)
        latest = meta.get("latest")
        if not latest:
            raise PromptError(
                f"meta.yaml for {name!r} does not declare a 'latest' version"
            )
        version = str(latest)

    if version not in versions:
        raise PromptNotFoundError(
            f"Prompt {name!r} has no version {version!r} (have: {', '.join(versions)})"
        )
    return version


def _read_template(name: str, version: str, role_file: str) -> str | None:
    path = _prompt_dir(name) / version / role_file
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    text = _COMMENT_RE.sub("", text)  # drop author-note comments before render
    return text.strip()


def load(
    name: str,
    version: str = "latest",
    *,
    variables: dict[str, Any] | None = None,
) -> RenderedPrompt:
    """Load and render a named, versioned prompt.

    Parameters
    ----------
    name:
        Prompt directory name under ``prompts/`` (e.g. ``"support_reply"``).
    version:
        ``"latest"`` (resolved via ``meta.yaml``) or a concrete ``"vN"``.
    variables:
        Values for the ``{{placeholders}}`` in the templates. Rendering raises
        if any placeholder is unsupplied or any supplied key is unused.

    Returns
    -------
    RenderedPrompt
        ``system`` text, the ``messages`` list, and the ``model`` + ``params``
        recorded in ``meta.yaml`` for this prompt.
    """
    variables = dict(variables or {})
    resolved = resolve_version(name, version)
    meta = _load_meta(name)

    system_template = _read_template(name, resolved, "system.md")
    user_template = _read_template(name, resolved, "user.md")

    if user_template is None:
        raise PromptNotFoundError(
            f"Prompt {name!r} {resolved} is missing user.md (a user template is required)"
        )

    # Render against the combined set of placeholders across both templates, so
    # a variable used only in system.md isn't flagged as "unknown" for user.md.
    combined = (system_template or "") + "\n" + user_template
    referenced = set(_PLACEHOLDER_RE.findall(combined))
    supplied = set(variables)

    missing = referenced - supplied
    if missing:
        raise MissingVariableError(
            "Missing variable(s) for template: " + ", ".join(sorted(missing))
        )
    unknown = supplied - referenced
    if unknown:
        raise UnknownVariableError(
            "Unknown variable(s) not used by template: " + ", ".join(sorted(unknown))
        )

    system_text = ""
    if system_template:
        # Per-template render: only the vars this template references.
        sys_vars = {k: variables[k] for k in _PLACEHOLDER_RE.findall(system_template)}
        system_text = render(system_template, sys_vars)

    user_vars = {k: variables[k] for k in _PLACEHOLDER_RE.findall(user_template)}
    user_text = render(user_template, user_vars)

    return RenderedPrompt(
        name=name,
        version=resolved,
        system=system_text,
        messages=[{"role": "user", "content": user_text}],
        model=str(meta.get("model", "")),
        params=dict(meta.get("params", {}) or {}),
    )


if __name__ == "__main__":
    # Tiny smoke demo: render the example prompt with placeholder values and
    # print what would go to the API. Safe to run — reads files only.
    rendered = load(
        "support_reply",
        "latest",
        variables={
            "company_name": "Acme Co.",
            "agent_name": "Sam",
            "customer_name": "Jordan",
            "customer_message": "My order hasn't arrived yet.",
            "tone": "warm and concise",
        },
    )
    print(f"# {rendered.name} ({rendered.version})  model={rendered.model}")
    print(f"params={rendered.params}\n")
    print("=== system ===")
    print(rendered.system or "(none)")
    print("\n=== messages ===")
    for msg in rendered.messages:
        print(f"[{msg['role']}]\n{msg['content']}")
