"""The RevOps workflow stages (PLAN -> ``workflow/``).

Each module is one stage of the revenue-motion busywork remover, and each composes a pattern
blueprint:

* :mod:`workflow.call_to_crm`    — transcript -> structured CRM fields, on the ``agent-loop`` (Ch 15).
* :mod:`workflow.enrich`         — external-data enrichment via the guarded MCP client.
* :mod:`workflow.draft_outreach` — ``rag-pipeline``-grounded follow-up, human-on-send (Ch 13/20).
* :mod:`workflow.schedules`      — nightly hygiene + enrichment jobs, traced (Ch 23/31).

It is a *workflow*, not a chat window: stages are explicit and composable, and the only thing
that ever leaves the building is a **drafted, unsent** email.
"""

from __future__ import annotations
