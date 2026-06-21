"""The copilot pipeline — compose the four pattern blueprints into one answer (Ch 16, 23).

This is where the solution *composes*. The individual stages already lean on patterns
(``nl_to_sql`` grounds on **rag-pipeline**, ``verify`` is the Ch-16 reasoning check, ``run`` is
the Ch-12/41 read-only tool). This module wires them into the senior shape the PLAN describes —
**generate -> verify -> execute (read-only) -> render**, *with the verification check before the
run* — and instruments the whole thing:

* **agent-loop** drives the act step. The verified, read-only query is exposed to an
  :class:`~agent_loop.AgentLoop` as a single ``run_sql`` tool; a deterministic mock model decides
  to call it. That is the honest composition: execution happens *through the agent loop's tool
  dispatch* (turn cap, error isolation, recovery) rather than a bare function call, so the
  copilot inherits the loop's hardening for free. Verification runs **before** the loop is even
  given the tool — a query that fails the check never becomes an executable tool call.
* **observability-stack** wraps each stage in a span (``retrieval`` / ``generate`` / ``verify`` /
  ``execute``) and records the generated SQL, row counts, and (mock) token cost, so a run renders
  as a readable trace tree — "trace generated SQL, query cost, and failures" (PLAN -> Composes).

The result is a :class:`CopilotAnswer` that carries the **SQL behind the answer** (the
"show me the SQL" affordance, Ch 20), the verification verdict, and the result rows — treated as a
copilot the human can inspect, not an oracle.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import _compose  # noqa: F401  (wires the pattern blueprints onto sys.path)
from .nl_to_sql import SqlGenerator, SqlPlan
from .run import DEFAULT_MAX_ROWS, DEFAULT_TIMEOUT_S, ExecutionError, QueryResult, run_query, warehouse_path
from .semantic import SemanticLayer, load_semantic_layer
from .verify import QueryVerifier, VerifyResult

# Composed pattern blueprints (after _compose put their src/ on sys.path).
from agent_loop import (  # noqa: E402
    AgentLoop,
    MockModel,
    ToolCall,
    ToolRegistry,
    assistant,
    tool as make_tool,
)
from observability_stack import ConsoleExporter, SpanKind, Tracer  # noqa: E402

MOCK = os.getenv("COMPANION_MOCK", "1") != "0"

# A nominal price tag for the mock "generate" step, so the trace shows a non-zero cost roll-up the
# way a live run would. Pure illustration — no tokens are actually spent in MOCK mode.
_MOCK_MODEL = "claude-sonnet-4"
_MOCK_INPUT_TOKENS = 420
_MOCK_OUTPUT_TOKENS = 90


@dataclass(frozen=True)
class CopilotAnswer:
    """The full, auditable outcome of one question.

    Carries everything a human (or an eval) needs to *trust or correct* the answer: the question,
    the generated ``sql`` (the "show me the SQL" affordance), the verification verdict, and the
    result. ``blocked`` answers carry the reasons and *no* rows — a refused query is a safe outcome,
    not a crash.
    """

    question: str
    sql: str
    plan: SqlPlan
    verify: VerifyResult
    result: QueryResult | None = None
    error: str = ""
    trace_text: str = ""

    @property
    def ok(self) -> bool:
        return self.verify.ok and self.result is not None and not self.error

    @property
    def blocked(self) -> bool:
        return self.verify.blocked

    def answer_rows(self) -> tuple[tuple, ...]:
        return self.result.rows if self.result is not None else ()

    def to_dict(self) -> dict:
        """JSON-able summary — what evals grade and what an API would return."""
        return {
            "question": self.question,
            "sql": self.sql,
            "verified": self.verify.ok,
            "verify_reasons": list(self.verify.reasons),
            "columns": list(self.result.columns) if self.result else [],
            "rows": [list(r) for r in self.answer_rows()],
            "error": self.error,
        }

    def render(self) -> str:
        """Console rendering: the answer *and* the SQL behind it (copilot, not oracle)."""
        head = f"Q: {self.question}"
        if self.verify.blocked:
            return f"{head}\n  [blocked] {self.verify.explain()}\n  SQL:\n{_indent(self.sql)}"
        if self.error:
            return f"{head}\n  [error] {self.error}\n  SQL:\n{_indent(self.sql)}"
        assert self.result is not None
        return (
            f"{head}\n"
            f"  {self.verify.explain()}\n"
            f"  Answer:\n{_indent(self.result.render())}\n"
            f"  SQL (show me the SQL):\n{_indent(self.sql)}"
        )


def _indent(text: str, pad: str = "    ") -> str:
    return "\n".join(pad + line for line in text.splitlines())


class AnalyticsCopilot:
    """NL question -> verified, read-only SQL -> result + the SQL behind it.

    Construct once (loads the semantic layer, builds the rag index, configures the verifier and
    the warehouse path); call :meth:`ask` per question. Each call composes the four patterns and
    returns a :class:`CopilotAnswer`. Set ``trace=True`` (the default) to attach a rendered
    observability trace to the answer.
    """

    def __init__(
        self,
        layer: SemanticLayer | None = None,
        *,
        db_path: str | Path | None = None,
        row_limit: int = DEFAULT_MAX_ROWS,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        require_limit: bool = True,
    ) -> None:
        self.layer = layer or load_semantic_layer()
        self.generator = SqlGenerator(self.layer, row_limit=row_limit)
        self.verifier = QueryVerifier(self.layer, require_limit=require_limit)
        self.db_path = Path(db_path) if db_path is not None else warehouse_path()
        self.row_limit = row_limit
        self.timeout_s = timeout_s

    def ask(self, question: str, *, trace: bool = True) -> CopilotAnswer:
        tracer = Tracer()
        with tracer.run("text-to-sql"):
            # 1) generate — grounded on the semantic layer via the rag-pipeline (Ch 13, 15).
            with tracer.model_span(
                "generate",
                model=_MOCK_MODEL,
                input_tokens=_MOCK_INPUT_TOKENS,
                output_tokens=_MOCK_OUTPUT_TOKENS,
            ) as gen_span:
                plan = self.generator.generate(question)
                gen_span.set_attribute("sql", plan.sql)
                gen_span.set_attribute("grounded_on", ", ".join(plan.retrieved[:3]))

            # 2) verify — the reasoning check BEFORE execution (Ch 16). A blocked plan
            #    short-circuits: it never becomes an executable tool call.
            with tracer.span("verify", SpanKind.CHAIN) as ver_span:
                verdict = self.verifier.verify(plan)
                ver_span.set_attribute("verified", verdict.ok)
                if verdict.blocked:
                    ver_span.set_attribute("reasons", "; ".join(verdict.reasons))

            if verdict.blocked:
                trace_text = self._export(tracer) if trace else ""
                return CopilotAnswer(
                    question=question, sql=plan.sql, plan=plan, verify=verdict,
                    trace_text=trace_text,
                )

            # 3) execute — through the AGENT LOOP's tool dispatch (read-only, row-capped, timed).
            result, error = self._execute_via_agent_loop(plan, tracer)

        trace_text = self._export(tracer) if trace else ""
        return CopilotAnswer(
            question=question, sql=plan.sql, plan=plan, verify=verdict,
            result=result, error=error, trace_text=trace_text,
        )

    def check_sql(self, sql: str, *, metric: str = "revenue") -> CopilotAnswer:
        """Verify (and, only if it passes, execute) a *raw* SQL string.

        This is the path a live LLM's raw output takes: a candidate query that did *not* come from
        the trusted mock planner. It exists so the safety contract can be tested honestly — the NL
        planner sanitizes input, so the only real test of the verifier is to hand it the kind of
        unsafe SQL a model might hallucinate. A blocked query never reaches the warehouse.
        """
        plan = SqlPlan(question=f"[raw sql] {sql[:60]}", sql=sql, metric=metric)
        verdict = self.verifier.verify(plan)
        if verdict.blocked:
            return CopilotAnswer(question=plan.question, sql=sql, plan=plan, verify=verdict)
        tracer = Tracer()
        with tracer.run("text-to-sql-raw"):
            result, error = self._execute_via_agent_loop(plan, tracer)
        return CopilotAnswer(
            question=plan.question, sql=sql, plan=plan, verify=verdict,
            result=result, error=error,
        )

    # -- composition with agent-loop ------------------------------------------------
    def _execute_via_agent_loop(
        self, plan: SqlPlan, tracer: Tracer
    ) -> tuple[QueryResult | None, str]:
        """Run the verified SQL as the agent loop's single tool.

        Composing the agent-loop here (rather than calling ``run_query`` directly) is deliberate:
        the loop gives us the turn cap, malformed-call repair, and failure isolation around the
        one risky step — touching the warehouse — so execution errors come back as readable
        results instead of exceptions. The ``execute`` span wraps the tool call for the trace.
        """
        captured: dict[str, QueryResult] = {}

        @make_tool(
            "run_sql",
            "Execute an already-verified, read-only SELECT against the warehouse and return rows.",
            {
                "type": "object",
                "properties": {"sql": {"type": "string", "description": "The verified SELECT."}},
                "required": ["sql"],
            },
        )
        def run_sql(sql: str) -> str:
            with tracer.tool_span("run_sql", attributes={"sql": sql}) as tool_span:
                res = run_query(
                    sql,
                    db_path=self.db_path,
                    max_rows=self.row_limit,
                    timeout_s=self.timeout_s,
                )
                captured["result"] = res
                tool_span.set_attribute("rows", res.row_count)
                tool_span.set_attribute("truncated", res.truncated)
                return f"{res.row_count} row(s); columns={list(res.columns)}"

        # A deterministic mock model: turn 1 calls run_sql with the verified SQL; turn 2 (after the
        # tool result lands) ends the loop with a short confirmation. No tokens, fully reproducible.
        model = MockModel(
            [
                assistant(
                    text="Running the verified query.",
                    tool_calls=(ToolCall(id="q1", name="run_sql", arguments={"sql": plan.sql}),),
                ),
                lambda transcript: assistant(text="Done; results returned to the analyst."),
            ]
        )
        loop = AgentLoop(model=model, tools=ToolRegistry([run_sql]), max_turns=3)

        with tracer.span("execute", SpanKind.CHAIN):
            outcome = loop.run(
                f"Answer this analytics question by running the verified SQL:\n{plan.sql}",
                system_prompt=(
                    "You are a read-only analytics executor. Call run_sql exactly once with the "
                    "verified SQL, then summarize."
                ),
            )

        if "result" in captured:
            return captured["result"], ""
        # The tool raised (ExecutionError surfaced as a failed tool turn) — report it cleanly.
        return None, _loop_error(outcome)

    def _export(self, tracer: Tracer) -> str:
        import io

        buf = io.StringIO()
        return ConsoleExporter(stream=buf).export(tracer.trace)


def _loop_error(outcome) -> str:
    """Pull the last tool error message out of an agent-loop transcript, if any."""
    for msg in reversed(list(outcome.transcript)):
        if msg.role == "tool" and msg.tool_result is not None and not msg.tool_result.ok:
            return msg.tool_result.content
    return f"execution did not complete (stop_reason={outcome.stop_reason.value})"


def answer_question(question: str, **kwargs) -> CopilotAnswer:
    """One-call convenience used by the demo and the evals."""
    return AnalyticsCopilot(**kwargs).ask(question)
