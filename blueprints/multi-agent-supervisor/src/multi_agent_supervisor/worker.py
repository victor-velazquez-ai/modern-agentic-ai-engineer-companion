"""A worker: a specialist agent the supervisor delegates to.

In the full repo a worker *is* an ``agent-loop`` (``../../agent-loop``): an
``observe → decide → act → observe`` cycle with a scoped toolset, driven by a model.
That blueprint is a planned sibling. To keep this pattern standalone and testable
today, :class:`Worker` carries a faithful, minimal loop here: it can call its scoped
tools and then ask the model to produce its answer. The seam is explicit — see
:meth:`Worker.run` and the ``agent_loop`` note in :func:`default_team`.

The supervisor only depends on the small surface :meth:`Worker.handle`, so swapping
in a real ``agent_loop.AgentLoop`` later changes nothing upstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping

from .guards import IterationGuard, Outcome, run_isolated
from .model import ModelPort

# A tool is just a named, pure-ish callable. Workers get a *scoped* set — capability
# confinement is a core multi-agent safety property (a writer can't run shell tools).
Tool = Callable[[str], str]


@dataclass
class WorkerResult:
    """What a worker hands back to the supervisor."""

    worker: str
    role: str
    task: str
    output: str
    tools_used: tuple[str, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class Worker:
    """A specialist with a name, a role, a scoped toolset, and a model.

    ``capabilities`` are free-form tags the router matches sub-tasks against
    (e.g. ``{"research", "search"}``). ``tools`` is the *only* set of side-effecting
    operations this worker may perform — the supervisor cannot widen it at call time.
    """

    name: str
    role: str
    model: ModelPort
    capabilities: frozenset[str] = field(default_factory=frozenset)
    tools: Mapping[str, Tool] = field(default_factory=dict)
    system_prompt: str | None = None
    max_tool_calls: int = 3

    def can_handle(self, tags: frozenset[str]) -> bool:
        """True if this worker advertises any of the requested capability tags."""
        return bool(self.capabilities & tags)

    # --- the agent-loop seam -------------------------------------------------
    def run(self, task: str) -> WorkerResult:
        """The worker's mini agent-loop: use scoped tools, then synthesize an answer.

        This is the place a real ``agent_loop.AgentLoop(model, tools=self.tools)``
        would drive the full observe→decide→act cycle. Here we run a bounded, legible
        version: deterministically invoke any tool whose name appears in the task,
        then ask the model to produce the final output with that tool context.
        """
        guard = IterationGuard(max_iterations=self.max_tool_calls)
        used: list[str] = []
        observations: list[str] = []
        for tool_name, tool in self.tools.items():
            if tool_name.lower() in task.lower():
                guard.tick()  # bound tool usage like a real loop bounds turns
                observations.append(f"[{tool_name}] {tool(task)}")
                used.append(tool_name)

        context = task if not observations else task + "\n\nTool observations:\n" + "\n".join(observations)
        system = self.system_prompt or f"You are {self.name}, a {self.role} specialist."
        resp = self.model.complete(context, system=system, role=self.role)
        return WorkerResult(
            worker=self.name,
            role=self.role,
            task=task,
            output=resp.text,
            tools_used=tuple(used),
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
        )

    def handle(self, task: str) -> Outcome[WorkerResult]:
        """Run the worker with failure isolation — the surface the supervisor calls.

        Returns an :class:`Outcome`, never raises for normal worker errors, so one
        bad worker degrades the team instead of aborting the whole run.
        """
        return run_isolated(lambda: self.run(task))


# --- a small, realistic default team used by the demo and tests ----------------
def _web_search(task: str) -> str:
    """Deterministic mock 'search' tool — returns canned hits, no network."""
    return f"3 sources found for: {task.strip()[:60]}"


def _word_count(text: str) -> str:
    return f"{len(text.split())} words"


def default_team(model: ModelPort) -> list[Worker]:
    """The canonical 2-worker team from the PLAN: a researcher and a writer.

    Real-repo note: each of these would be constructed as
    ``Worker(..., agent=AgentLoop(model, tools=...))`` using ``../../agent-loop``.
    The scoped toolsets below show the confinement that makes multi-agent safe.
    """
    researcher = Worker(
        name="researcher",
        role="research",
        model=model,
        capabilities=frozenset({"research", "search", "investigate", "find", "facts"}),
        tools={"search": _web_search},
        system_prompt="You are a meticulous research analyst. Gather and verify facts.",
    )
    writer = Worker(
        name="writer",
        role="writing",
        model=model,
        capabilities=frozenset({"write", "writing", "summarize", "draft", "explain", "report"}),
        tools={"count": _word_count},
        system_prompt="You are a sharp technical writer. Turn findings into clear prose.",
    )
    return [researcher, writer]
