"""The agent: where your tool-use loop goes.

This is a **stub**. Out of the box ``run(prompt)`` makes a single model call through
the one LLM door (``llm.complete``) and returns the reply — enough for the project to
run end-to-end in MOCK mode with no API spend. The real tool-use loop is yours to
build; the scaffolding you need is already here:

  * ``app.tools.tool_definitions()`` — the schemas to advertise to the model.
  * ``app.tools.run_tool(name, input)`` — dispatch a tool call to its handler.
  * ``app.llm.complete(...)`` — the single door to the model.

See the chapter's "Tool Use & Function Calling" build (the hardened version lives in
``blueprints/agent-loop/``) for the loop you replace this stub with.
"""

from __future__ import annotations

from app.config import Settings, get_settings
from app.llm import complete
from app.tools import tool_definitions

# Edit to shape your agent's behavior. Kept short on purpose.
SYSTEM_PROMPT = "You are a helpful assistant. Use a tool when it would help; otherwise answer directly."


def run(prompt: str, *, settings: Settings | None = None) -> str:
    """Run the agent on a single ``prompt`` and return its final text answer.

    The stub does a single completion. Replace the body with your tool-use loop.
    """
    settings = settings or get_settings()

    # The tools are registered and ready to advertise to the model. The stub doesn't
    # use them yet — referencing them here keeps the wiring visible (and the import live)
    # for when you build the loop.
    _tools = tool_definitions()

    # TODO: your tool-use loop.
    #   while True:
    #       response = call the model with `prompt`, SYSTEM_PROMPT, and `_tools`
    #       if response.stop_reason != "tool_use":
    #           return the final text
    #       for each tool_use block:
    #           result = run_tool(block.name, block.input)
    #           append the tool_result and continue the loop
    #
    # Until then, the stub returns a single completion so the project runs end-to-end.
    return complete(prompt, settings=settings)
