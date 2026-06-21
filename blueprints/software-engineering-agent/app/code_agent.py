"""code_agent — the agent-loop that fixes a failing test behind the oracle (Ch 12, 16).

This is the heart of the solution and the clearest place to see the composition:

* the **loop** is the ``agent-loop`` blueprint (``observe → decide → act → observe``), unmodified;
* the **hands** are the sandboxed, least-privilege tools from ``tools/sandbox_mock.py`` (built on
  the ``mcp-server`` blueprint's :class:`~mcp_server.Tool`) — read, list, write, *confined to the
  repo*, no shell, no network, no prod;
* the **verification loop** is ``ci/oracle.py`` (the ``eval-harness`` blueprint): a proposed change
  is accepted **only if the oracle goes green** — tests pass, the code still compiles, and no
  assertion was deleted to fake it;
* the **trace** is the ``observability-stack`` blueprint: the whole run is one span tree with the
  oracle verdict attached, so a failed run is debuggable.

The agent never auto-merges. On a green oracle it hands back a :class:`~app.pr.PullRequest` for a
human to review; on a red oracle it reverts its write and reports the failure. **The AI writes the
code; you own the merge.**

MOCK by default
---------------
``COMPANION_MOCK=1`` (the default) drives the loop with a deterministic
:class:`~agent_loop.MockModel` script: list the repo, read the red test, read the buggy source,
write the one-token fix. No API key, no spend, identical every run. The script is exactly what a
real model would be *asked* to do; swap in a gateway-backed :class:`~agent_loop.ModelPort` to go
live and nothing else changes.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# --- composition seam: put the sibling pattern blueprints + local tool/ci modules on the path ----
_SOLUTION_ROOT = Path(__file__).resolve().parent.parent
if str(_SOLUTION_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOLUTION_ROOT))

from _blueprints import ensure_blueprints_on_path, repo_root as _bundled_repo_root  # noqa: E402

ensure_blueprints_on_path()
# ``tools/`` and ``ci/`` are plain script dirs (no package), so add them and import by module name.
for _sub in ("tools", "ci"):
    _d = str(_SOLUTION_ROOT / _sub)
    if _d not in sys.path:
        sys.path.insert(0, _d)

from agent_loop import (  # noqa: E402  (the loop — reused, not forked)
    AgentLoop,
    MockModel,
    ToolCall,
    ToolRegistry,
    assistant,
)
from agent_loop import Tool as LoopTool  # noqa: E402
from agent_loop import ToolSpec as LoopToolSpec  # noqa: E402

import oracle as _oracle  # noqa: E402  (ci/oracle.py — the eval-harness verification loop)
import sandbox_mock as _sandbox  # noqa: E402  (tools/sandbox_mock.py — mcp-server-backed tools)

# Optional: trace the run with the observability-stack blueprint, but never *require* it.
try:  # pragma: no cover - the import either works (blueprint present) or we no-op
    from observability_stack import SpanKind, Tracer  # noqa: E402

    _OBSERVABILITY = True
except Exception:  # pragma: no cover - tracing is a nicety, not a dependency
    _OBSERVABILITY = False


# ------------------------------------------------------------------------------------------------
# Bridge: an mcp-server Tool (validated handler) → an agent-loop Tool (schema + fn).
# ------------------------------------------------------------------------------------------------

def _as_loop_tool(mcp_tool: "_sandbox.Tool") -> LoopTool:
    """Adapt one ``mcp_server.Tool`` into an ``agent_loop.Tool``.

    The mcp-server tool already validates its arguments against the schema and runs its handler
    behind the sandbox; we wrap that as the loop's ``fn`` and reuse the same JSON-Schema as the
    loop's spec. A :class:`~mcp_server.ToolError` (including a :class:`SandboxViolation`) becomes a
    string the loop turns into a recoverable error result — the model reads it and corrects.
    """

    def _fn(**kwargs: Any) -> Any:
        try:
            return mcp_tool.call(kwargs)
        except _sandbox.ToolError as exc:
            # Surface as a readable failure; the loop wraps it into an ok=False ToolResult.
            return f"ERROR: {exc}"

    return LoopTool(
        spec=LoopToolSpec(
            name=mcp_tool.name,
            description=mcp_tool.description,
            parameters=mcp_tool.input_schema,
        ),
        fn=_fn,
    )


def _loop_tools_for(sandbox: "_sandbox.Sandbox") -> ToolRegistry:
    """The least-privilege repo toolset, exposed to the agent loop."""
    return ToolRegistry([_as_loop_tool(t) for t in _sandbox.build_repo_tools(sandbox)])


# ------------------------------------------------------------------------------------------------
# The deterministic MOCK "brain": what a real model would do, scripted so the demo spends nothing.
# ------------------------------------------------------------------------------------------------

def _slugify_fix_script(target_rel: str = "src/textkit.py") -> list[Any]:
    """A canned agent script that fixes the bundled ``slugify`` bug.

    Mirrors a real model's plan: (1) list the repo, (2) read the red test, (3) read the buggy
    source, (4) propose the one-token fix as a ``write_file`` call, (5) declare done. Each step is
    an assistant turn; the loop executes the tool calls against the sandbox between them.

    The fix itself is the minimal change the verification loop can prove correct: replace the
    separator-dropping ``"".join(words)`` with ``sep.join(words)``.
    """

    def _read_then_fix(transcript: list[Any]) -> Any:
        """Read the current source off the transcript, apply the one-token fix, write it back."""
        source = _last_tool_text(transcript, "read_file") or ""
        fixed = source.replace('return "".join(words)', "return sep.join(words)")
        return assistant(
            text="The bug is the empty separator in slugify's join; applying sep.join.",
            tool_calls=(
                ToolCall(
                    id="w1",
                    name="write_file",
                    arguments={"path": target_rel, "content": fixed},
                ),
            ),
        )

    return [
        assistant(
            text="Let me see the repository layout.",
            tool_calls=(ToolCall(id="l1", name="list_files", arguments={}),),
        ),
        assistant(
            text="Reading the failing test to learn the expected behaviour.",
            tool_calls=(
                ToolCall(
                    id="t1",
                    name="read_file",
                    arguments={"path": "tests/test_slugify.py"},
                ),
            ),
        ),
        assistant(
            text="Reading the source under test.",
            tool_calls=(
                ToolCall(id="r1", name="read_file", arguments={"path": target_rel}),
            ),
        ),
        _read_then_fix,
        assistant(text="Fix written. The oracle will now verify it."),
    ]


def _last_tool_text(transcript: list[Any], tool_name: str) -> str | None:
    """Pull the content of the most recent successful ``tool_name`` result from the transcript."""
    for msg in reversed(transcript):
        result = getattr(msg, "tool_result", None)
        if result is not None and result.name == tool_name and result.ok:
            # The sandbox returns a dict repr (e.g. "{'path': ..., 'content': '...'}").
            return _extract_content_field(msg.text)
    return None


def _extract_content_field(text: str) -> str | None:
    """Best-effort: recover the ``content`` value from a stringified read_file result.

    The loop stringifies the tool's dict return; for a deterministic mock we parse it back with
    :func:`ast.literal_eval`. A real model never needs this — it reads the text directly.
    """
    import ast

    try:
        obj = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text
    if isinstance(obj, dict) and "content" in obj:
        return str(obj["content"])
    return text


# ------------------------------------------------------------------------------------------------
# The agent.
# ------------------------------------------------------------------------------------------------

@dataclass
class FixAttempt:
    """The outcome of one fix run: what changed, and whether the oracle accepted it."""

    accepted: bool
    oracle_report: str
    changes: dict[str, tuple[str, str]] = field(default_factory=dict)
    stop_reason: str = ""
    turns: int = 0

    @property
    def ok(self) -> bool:
        return self.accepted


@dataclass
class CodeAgent:
    """Fix one failing test in a repo, gated by the oracle, packaged as a PR.

    The agent works on a **copy** of the target repo (a working tree under a temp dir) so a run is
    idempotent and never mutates the bundled ``sample_repo/``. It:

    1. captures the assertion baseline (so a deleted assertion can be detected),
    2. drives the ``agent-loop`` with its scoped sandbox tools to propose and write a change,
    3. runs the **oracle** (``ci/oracle.py``) over the modified tree,
    4. **accepts only on a green oracle** — otherwise it reverts the write — and
    5. returns a :class:`FixAttempt` the caller turns into a :class:`~app.pr.PullRequest`.

    Construct via :func:`build_agent`. ``model`` defaults to the offline MockModel script; inject a
    gateway-backed ``ModelPort`` for the live path with no other change.
    """

    source_repo: Path
    model_factory: Callable[[], Any]
    max_turns: int = 8
    trace: bool = True

    def fix(self, target_rel: str = "src/textkit.py") -> FixAttempt:
        """Run the fix loop against a working copy of the repo and gate it with the oracle."""
        workdir = Path(tempfile.mkdtemp(prefix="seagent-fix-"))
        work_repo = workdir / "repo"
        shutil.copytree(self.source_repo, work_repo)
        try:
            return self._fix_in(work_repo, target_rel)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def _fix_in(self, work_repo: Path, target_rel: str) -> FixAttempt:
        before = _read(work_repo / target_rel)
        baseline_assertions = _oracle.count_assertions(work_repo)

        sandbox = _sandbox.Sandbox(root=work_repo)
        tools = _loop_tools_for(sandbox)

        tracer = Tracer() if (self.trace and _OBSERVABILITY) else None
        if tracer is not None:
            with tracer.run("code-agent-fix"):
                self._drive_loop(tools)
                report = _oracle.evaluate(work_repo, baseline_assertions=baseline_assertions)
                span = tracer.current_span()
                if span is not None:
                    span.set_attribute("oracle.passed", report.passed)
        else:
            self._drive_loop(tools)
            report = _oracle.evaluate(work_repo, baseline_assertions=baseline_assertions)

        after = _read(work_repo / target_rel)
        if report.passed:
            return FixAttempt(
                accepted=True,
                oracle_report=report.render(),
                changes={target_rel: (before, after)} if before != after else {},
            )
        # Red oracle: reject and revert the write so a bad change never leaves the sandbox.
        _write(work_repo / target_rel, before)
        return FixAttempt(accepted=False, oracle_report=report.render(), changes={})

    def _drive_loop(self, tools: ToolRegistry) -> None:
        """Run the agent-loop once with the configured (mock or live) model."""
        loop = AgentLoop(model=self.model_factory(), tools=tools, max_turns=self.max_turns)
        loop.run(
            "A test is failing. Read the failing test and the source it covers, then write the "
            "minimal fix. Do not edit tests.",
            system_prompt=(
                "You are a software-engineering agent. You may read, list, and write files in the "
                "repository only. You have no shell and no network. Make the smallest change that "
                "turns the suite green; never weaken a test."
            ),
        )


def build_agent(
    *,
    source_repo: Path | str | None = None,
    model: Callable[[], Any] | None = None,
    max_turns: int = 8,
    trace: bool = True,
) -> CodeAgent:
    """Construct a :class:`CodeAgent`.

    ``source_repo`` defaults to the bundled ``sample_repo/``. ``model`` is a *factory* returning a
    fresh :class:`~agent_loop.ModelPort` per run (the mock is single-use because its script is
    consumed); the default is the deterministic slugify-fix script. Pass your own factory — e.g.
    one returning a gateway-backed port — to go live.
    """
    repo = Path(source_repo) if source_repo is not None else _bundled_repo_root()
    factory = model if model is not None else (lambda: MockModel(_slugify_fix_script()))
    return CodeAgent(
        source_repo=Path(repo).resolve(),
        model_factory=factory,
        max_turns=max_turns,
        trace=trace,
    )


# --- tiny IO helpers ----------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def mock_enabled() -> bool:
    """Whether we run offline (the default). Mirrors the sibling blueprints' switch."""
    return os.getenv("COMPANION_MOCK", "1").strip().lower() not in {"0", "false", "no"}
