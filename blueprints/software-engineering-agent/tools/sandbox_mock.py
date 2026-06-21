"""Sandboxed, least-privilege repo tools (Ch 12, 41) — the agent's only hands.

A software-engineering agent is exactly as safe as the tools you give it. This module is the
**capability boundary**: the agent can read files, list the tree, write a file, and *propose* a
patch — and it can do **none of that outside the repo root**, touch the network, or run a shell.
Everything dangerous is simply not exposed.

Composition
-----------
The tool *shape* (name + JSON-schema + pure handler, validated before the handler runs) is the
``mcp-server`` blueprint's :class:`~mcp_server.tools.Tool`. We reuse it directly rather than
reinventing tool-arg validation: ``mcp_server.validate_args`` rejects bad calls at the boundary,
which is the least-privilege posture we want. The handlers below are confined to a ``Sandbox``
rooted at the target repo.

Why "mock"? The filesystem operations are real (on the bundled ``sample_repo/``), but there is
**no exec, no network, no prod access** — the genuinely dangerous capabilities are stubbed to
*refused*. Point this at a real sandbox/runner (a container, a jail) to go live; the schemas and
the confinement contract do not change. **Never grant production access.**
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

# Make the sibling pattern blueprints importable (compose, don't fork).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _blueprints import ensure_blueprints_on_path  # noqa: E402

ensure_blueprints_on_path()

from mcp_server import Tool, ToolError  # noqa: E402  (reused from the mcp-server blueprint)


class SandboxViolation(ToolError):
    """Raised when a tool call tries to escape the sandbox (path traversal, prod path, network).

    It subclasses ``mcp_server.ToolError`` so the agent loop reports it back as a readable,
    recoverable tool result rather than a crash — the model reads "path escapes the sandbox" and
    corrects its call.
    """


@dataclass
class Sandbox:
    """A repo confined to one root directory. The agent cannot see or touch anything else.

    Every path the agent passes is resolved and checked to stay under ``root``; symlinks and
    ``..`` traversal are rejected. This is the single chokepoint that makes "give an LLM file
    tools" defensible — confine first, capabilities second.
    """

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        if not self.root.is_dir():
            raise SandboxViolation(f"sandbox root does not exist: {self.root}")

    # --- the confinement primitive -------------------------------------------------------
    def _resolve(self, rel: str) -> Path:
        """Resolve ``rel`` against the root and refuse anything that escapes it."""
        if not isinstance(rel, str) or not rel.strip():
            raise SandboxViolation("path must be a non-empty relative string")
        candidate = (self.root / rel).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise SandboxViolation(
                f"path {rel!r} escapes the sandbox root; only files under the repo are allowed"
            ) from None
        return candidate

    # --- read-only capabilities ----------------------------------------------------------
    def read_file(self, args: Mapping[str, Any]) -> dict[str, Any]:
        path = self._resolve(args["path"])
        if not path.is_file():
            raise SandboxViolation(f"no such file in repo: {args['path']!r}")
        return {"path": args["path"], "content": path.read_text(encoding="utf-8")}

    def list_files(self, args: Mapping[str, Any]) -> dict[str, Any]:
        sub = args.get("subdir", ".")
        base = self._resolve(sub)
        if not base.is_dir():
            raise SandboxViolation(f"no such directory in repo: {sub!r}")
        files = sorted(
            str(p.relative_to(self.root)).replace("\\", "/")
            for p in base.rglob("*.py")
            if p.is_file()
        )
        return {"subdir": sub, "files": files}

    # --- write capability (still confined) -----------------------------------------------
    def write_file(self, args: Mapping[str, Any]) -> dict[str, Any]:
        """Overwrite a file *inside the repo*. The only mutating capability the agent has.

        This is what applies an accepted patch. It is intentionally separate from the oracle:
        the agent may write, but a write only becomes a *change* the human sees once the oracle
        passes (``ci/oracle.py``) and ``pr.py`` packages it — never an auto-merge.
        """
        path = self._resolve(args["path"])
        if not path.parent.is_dir():
            raise SandboxViolation(f"parent directory does not exist for {args['path']!r}")
        before = path.read_text(encoding="utf-8") if path.is_file() else ""
        path.write_text(args["content"], encoding="utf-8")
        return {"path": args["path"], "bytes": len(args["content"]), "changed": before != args["content"]}

    # --- refused capabilities (documented denials) ---------------------------------------
    @staticmethod
    def run_shell(args: Mapping[str, Any]) -> dict[str, Any]:
        """Refused by design. A code agent must not have an arbitrary shell.

        Tests run through the *oracle* (a fixed, in-process command), never an open ``exec``.
        Exposing this as an explicit refusal — rather than omitting it — documents the boundary
        and gives the model a readable "not allowed" instead of a mysterious missing tool.
        """
        raise SandboxViolation(
            "shell execution is not permitted in this sandbox. Run the test suite via the oracle, "
            "which uses a fixed command with no production or network access."
        )


# --- the tool catalogue the agent loop sees -------------------------------------------------

def build_repo_tools(sandbox: Sandbox) -> list[Tool]:
    """The least-privilege toolset exposed to the agent, as ``mcp-server`` ``Tool`` objects.

    Read, list, and write — confined to the repo. No shell, no network, no prod. Each tool's
    args are validated against its schema by ``mcp_server`` *before* the handler runs, so a
    malformed call is a clean error result, not an exception.
    """
    return [
        Tool(
            name="read_file",
            description="Read one UTF-8 text file from the repository (path is repo-relative).",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string", "maxLength": 400}},
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=sandbox.read_file,
        ),
        Tool(
            name="list_files",
            description="List .py files under a repo-relative subdirectory (defaults to the root).",
            input_schema={
                "type": "object",
                "properties": {"subdir": {"type": "string", "maxLength": 400}},
                "required": [],
                "additionalProperties": False,
            },
            handler=sandbox.list_files,
        ),
        Tool(
            name="write_file",
            description="Overwrite one repo-relative file with new content (used to apply a patch).",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "maxLength": 400},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
            handler=sandbox.write_file,
        ),
    ]
