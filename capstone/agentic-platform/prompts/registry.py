"""The versioned prompt registry loader (Ch 10).

Loads a *named, versioned* prompt from this directory and renders it into the
message list you pass to the model layer (``llm/``). Prompts live in Markdown
files, not inline f-strings, so they diff cleanly, review well, and can be
pinned/rolled back like any other code.

Resolution is **deterministic**: ``"latest"`` reads the ``latest`` pointer in the
prompt's ``meta.yaml`` — not "whatever sorts highest on disk" — so shipping a new
version is moving one line, and rollback is moving it back.

This module reads files and substitutes variables only. There is **no business
logic, no network, and no secrets** here; example variable values in prompt files
are placeholders, never real data.

Dependencies: uses PyYAML when available; falls back to a tiny built-in parser for
the small flat ``meta.yaml`` files this registry ships, so the registry imports
and runs with no extra dependency (consistent with the repo's mock-first stance).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# The prompts/ directory is this file's own directory (the prompt folders live
# next to registry.py).
PROMPTS_DIR = Path(__file__).resolve().parent

# {{ variable_name }} with optional surrounding whitespace.
_PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")

# HTML comments are author notes — stripped before rendering so guidance never
# reaches the model or gets mis-parsed as a placeholder.
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


class PromptError(Exception):
    """Base class for every error this module raises."""


class PromptNotFoundError(PromptError):
    """The named prompt or the requested version does not exist on disk."""


class MissingVariableError(PromptError):
    """A template referenced a ``{{variable}}`` that was not supplied."""


class UnknownVariableError(PromptError):
    """A variable was supplied that the template never references.

    Treated as an error on purpose: an unused variable almost always means a typo
    or a stale call site, and silently dropping it hides bugs.
    """


@dataclass(frozen=True)
class RenderedPrompt:
    """The result of :func:`load` — ready to hand to the model layer.

    ``messages`` is the ``messages=[...]`` argument; ``system`` is the top-level
    system string (empty if the prompt has no system template). ``model`` and
    ``params`` come from ``meta.yaml`` so the call site uses the exact model +
    settings this prompt version was tuned for.
    """

    name: str
    version: str
    system: str
    messages: list[dict[str, str]]
    model: str
    params: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# YAML loading (PyYAML if present, else a tiny flat-file fallback)
# ---------------------------------------------------------------------------


def _load_yaml(text: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise PromptError("meta.yaml must be a mapping")
        return data
    except ImportError:
        return _parse_simple_yaml(text)


def _coerce_scalar(value: str) -> Any:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~", ""):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Minimal YAML for the flat ``meta.yaml`` files this registry ships.

    Handles top-level ``key: value`` pairs and one level of nested mappings under
    a bare ``key:`` (used for ``params:``). Block scalars (``>-``) collapse to a
    single string. This is *not* a general YAML parser — it exists only so the
    registry runs without PyYAML; install PyYAML for anything richer.
    """

    root: dict[str, Any] = {}
    current_key: str | None = None
    current_map: dict[str, Any] | None = None
    block_lines: list[str] | None = None
    block_key: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if block_lines is not None and indent > 0 and ":" not in stripped:
            block_lines.append(stripped)
            continue
        if block_lines is not None and block_key is not None:
            root[block_key] = " ".join(block_lines).strip()
            block_lines = None
            block_key = None

        if indent == 0:
            current_key, _, value = stripped.partition(":")
            current_key = current_key.strip()
            value = value.strip()
            if value in (">-", ">", "|", "|-"):
                block_key = current_key
                block_lines = []
                current_map = None
            elif value == "":
                current_map = {}
                root[current_key] = current_map
            else:
                root[current_key] = _coerce_scalar(value)
                current_map = None
        else:
            if current_map is None:
                continue
            sub_key, _, sub_value = stripped.partition(":")
            sub_value = sub_value.strip()
            if sub_value == "":
                nested: dict[str, Any] = {}
                current_map[sub_key.strip()] = nested
                current_map = nested
            else:
                current_map[sub_key.strip()] = _coerce_scalar(sub_value)

    if block_lines is not None and block_key is not None:
        root[block_key] = " ".join(block_lines).strip()
    return root


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render(template: str, variables: dict[str, Any]) -> str:
    """Fill ``{{placeholders}}`` in ``template`` from ``variables``.

    Raises :class:`MissingVariableError` if the template references a variable
    that is absent, and :class:`UnknownVariableError` if ``variables`` contains a
    key the template never uses. Both failures are loud by design.
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


# ---------------------------------------------------------------------------
# Discovery + resolution
# ---------------------------------------------------------------------------


def _prompt_dir(name: str) -> Path:
    directory = PROMPTS_DIR / name
    if not directory.is_dir():
        raise PromptNotFoundError(f"No prompt named {name!r} under {PROMPTS_DIR}")
    return directory


def _load_meta(name: str) -> dict[str, Any]:
    meta_path = _prompt_dir(name) / "meta.yaml"
    if not meta_path.is_file():
        raise PromptNotFoundError(f"Prompt {name!r} has no meta.yaml")
    return _load_yaml(meta_path.read_text(encoding="utf-8"))


def _version_key(version: str) -> int:
    match = re.fullmatch(r"v(\d+)", version)
    return int(match.group(1)) if match else -1


def available_prompts() -> list[str]:
    """Every prompt name discoverable under ``prompts/``."""

    if not PROMPTS_DIR.is_dir():
        return []
    return sorted(
        p.name
        for p in PROMPTS_DIR.iterdir()
        if p.is_dir() and (p / "meta.yaml").is_file()
    )


def list_versions(name: str) -> list[str]:
    """The available ``vN`` version ids for ``name``, sorted ascending."""

    directory = _prompt_dir(name)
    versions = [
        p.name
        for p in directory.iterdir()
        if p.is_dir() and re.fullmatch(r"v\d+", p.name)
    ]
    return sorted(versions, key=_version_key)


def resolve_version(name: str, version: str = "latest") -> str:
    """Resolve ``"latest"`` to a concrete ``vN`` using ``meta.yaml`` (deterministic)."""

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
    text = _COMMENT_RE.sub("", path.read_text(encoding="utf-8"))
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
        Prompt directory name under ``prompts/`` (e.g. ``"triage_ticket"``).
    version:
        ``"latest"`` (resolved via ``meta.yaml``) or a concrete ``"vN"``.
    variables:
        Values for the ``{{placeholders}}`` across the templates. Raises if any
        placeholder is unsupplied or any supplied key is unused.

    Returns
    -------
    RenderedPrompt
        ``system`` text, the ``messages`` list, and the ``model`` + ``params``
        recorded in ``meta.yaml`` for this version.
    """

    variables = dict(variables or {})
    resolved = resolve_version(name, version)
    meta = _load_meta(name)

    system_template = _read_template(name, resolved, "system.md")
    user_template = _read_template(name, resolved, "user.md")
    if user_template is None:
        raise PromptNotFoundError(
            f"Prompt {name!r} {resolved} is missing user.md (required)"
        )

    # Validate against the union of placeholders across both templates.
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
    # Smoke demo: render the example prompt and print what would go to the model.
    rendered = load(
        "triage_ticket",
        "latest",
        variables={
            "product_name": "Acme Platform",
            "categories": "billing, bug, feature_request, account",
            "ticket_text": "I was charged twice for my subscription this month.",
        },
    )
    print(f"# {rendered.name} ({rendered.version})  model={rendered.model}")
    print(f"params={rendered.params}\n")
    print("=== system ===")
    print(rendered.system or "(none)")
    print("\n=== messages ===")
    for msg in rendered.messages:
        print(f"[{msg['role']}]\n{msg['content']}")
