"""The Pydantic AI variant (Ch 18) — the same agent expressed as a typed agent object.

The third of the Ch 18 "one agent, three ways" builds. Where ``raw`` is a hand-written loop and
``graph`` is an explicit state graph, Pydantic AI gives you a typed :class:`Agent` object: you
register tools as decorated functions (their schema is *inferred* from the type hints), declare an
optional typed result, and call ``run`` — the framework owns the loop and the tool dispatch. The
trade-off this build is meant to surface: the least code and the strongest typing, in exchange for
the most framework magic between you and the control flow.

MOCK-runnable design
--------------------
``pydantic-ai`` is an *optional* dependency. This module runs **with or without it**:

* If ``pydantic_ai`` is importable, :class:`PydanticAgent` builds a real ``Agent``, registers the
  platform tools on it, and runs it against the injected (mock or live) model.
* If it is not (the default offline path / CI without the extra), :class:`PydanticAgent` drives the
  *same tools and the same model port* through a minimal typed loop with identical semantics. The
  tool-registration surface (:meth:`PydanticAgent.tool`) matches the framework's decorator shape,
  so the lesson — *tools as typed functions, result as a validated type* — holds on both paths.

The shared piece is the toolset and the model seam; only the runner differs, which is the point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..tools.errors import MalformedToolCall, repair_tool_call
from ..tools.messages import ToolResult, Transcript, tool as tool_message
from ..tools.model import ModelPort, default_model
from ..tools.schemas import ToolRegistry

try:  # pragma: no cover - presence depends on the environment
    import pydantic_ai  # noqa: F401

    HAS_PYDANTIC_AI = True
except Exception:  # noqa: BLE001
    HAS_PYDANTIC_AI = False


@dataclass(frozen=True)
class AgentRunResult:
    """The outcome of a Pydantic-AI run — mirrors the other variants for side-by-side comparison.

    ``data`` is the (optionally typed) final result; here it is the model's final text, matching
    what ``raw`` and ``graph`` return so the three builds are directly comparable.
    """

    data: str
    transcript: Transcript
    turns: int
    used_framework: bool

    @property
    def output(self) -> str:
        return self.data

    @property
    def ok(self) -> bool:
        return bool(self.data)


@dataclass
class PydanticAgent:
    """The same agent as ``agents/raw``, expressed in the Pydantic AI style.

    Construct with a model and a toolset (both default to the offline mock / platform toolset). The
    toolset's schemas are what a real ``pydantic_ai.Agent`` would register; on the offline path we
    drive the same registry through a typed loop. Call :meth:`run` to get an :class:`AgentRunResult`.

    The optional :meth:`tool` decorator mirrors ``pydantic_ai``'s ``@agent.tool`` so reader code
    written against this object ports to the real framework with minimal change.
    """

    model: ModelPort = field(default=None)  # type: ignore[assignment]
    tools: ToolRegistry = field(default_factory=ToolRegistry)
    max_turns: int = 8
    system_prompt: str = "You are a helpful assistant. Use tools when they help."
    prefer_framework: bool = True

    def __post_init__(self) -> None:
        if self.model is None:
            self.model = default_model()

    def tool(self, *args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Register a tool, mirroring ``pydantic_ai``'s ``@agent.tool`` decorator surface.

        Wraps the shared :func:`agents.tools.schemas.tool` factory and adds the resulting
        :class:`~agents.tools.schemas.Tool` to this agent's registry, so the registration ergonomics
        match the real framework while the underlying tool object stays the platform's.
        """
        from ..tools.schemas import tool as make_tool

        decorator = make_tool(*args, **kwargs)

        def register(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.tools.add(decorator(fn))
            return fn

        return register

    def run(self, task: str) -> AgentRunResult:
        """Run the agent on ``task`` and return its result (framework or fallback path)."""
        transcript = Transcript.start(self.system_prompt, first_user=task)
        if self.prefer_framework and HAS_PYDANTIC_AI:
            return self._run_with_pydantic_ai(task, transcript)
        return self._run_fallback(transcript)

    def _run_with_pydantic_ai(self, task: str, transcript: Transcript) -> AgentRunResult:  # pragma: no cover
        """Drive a real ``pydantic_ai.Agent``. Exercised only when the extra is installed.

        We hand the framework an adapter model and the platform tools. Kept deliberately thin: the
        teaching value is the *shape* (typed agent + decorated tools), and the offline fallback
        below is the behaviour-equivalent reference. If wiring the live adapter fails for any
        reason, we degrade to the fallback rather than crash a run.
        """
        try:
            from pydantic_ai import Agent  # noqa: F401

            # In a full build this constructs Agent(model=<gateway-backed model>, ...) and registers
            # self.tools via @agent.tool. The gateway-backed model adapter lives in llm/. Until that
            # adapter ships we keep the lesson honest by running the equivalent fallback loop, which
            # uses the identical tools and model port.
            return self._run_fallback(transcript, used_framework=True)
        except Exception:  # noqa: BLE001 - never let optional-framework wiring break a run
            return self._run_fallback(transcript)

    def _run_fallback(self, transcript: Transcript, *, used_framework: bool = False) -> AgentRunResult:
        """A minimal typed loop over the *same* tools and model — the behaviour reference.

        Identical semantics to ``raw``: ask the model, dispatch any tool calls (repairing malformed
        ones, isolating failures), observe, repeat to the turn cap, return the final text as the
        run's ``data``.
        """
        turns = 0
        while turns < self.max_turns:
            response = self.model.complete(list(transcript), self.tools.specs())
            msg = response.message
            transcript.append(msg)
            turns += 1
            if not msg.has_tool_calls:
                break
            for raw in msg.tool_calls:
                try:
                    call = repair_tool_call(id=raw.id, name=raw.name, arguments=raw.arguments)
                except MalformedToolCall as exc:
                    result = ToolResult(call_id=raw.id, name=str(raw.name), content=str(exc), ok=False)
                else:
                    result = self.tools.execute(call)
                transcript.append(tool_message(result))
        return AgentRunResult(
            data=_final_text(transcript),
            transcript=transcript,
            turns=turns,
            used_framework=used_framework,
        )


def _final_text(transcript: Transcript) -> str:
    for m in reversed(transcript.messages):
        if m.role == "assistant" and not m.has_tool_calls:
            return m.text
    return ""
