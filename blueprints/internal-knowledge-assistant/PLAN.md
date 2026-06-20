# Blueprint — Internal Knowledge Assistant / Employee Copilot  (solution)

> Appendix G use case · Status: 📋 planned (Phase 1)

## The problem it solves
Institutional knowledge is technically written down but practically unfindable, so the real
interface to it is interrupting a senior person. Almost every function buys a version of
this (IT, HR, ops, finance, engineering onboarding) to recover time on both sides and reduce
policy-violation mistakes made from ignorance.

## What it does
An assistant that answers employees from the company's own knowledge — wikis, policy docs,
drives, runbooks, Slack history, ticket archives — with grounded, cited answers, and
optionally light tool use to file a ticket or open a request. Its **defining constraint is
permissions**: an employee must never retrieve content their identity cannot already access
(Appendix G → "Internal knowledge assistant"; Ch 43 enterprise RAG assistant).

## Composes (pattern blueprints used)
- [`../rag-pipeline/`](../rag-pipeline/) — permissioned hybrid retrieval + reranking + inline citations; ingestion carries each doc's ACL metadata into the index (Ch 13, 43).
- [`../agent-loop/`](../agent-loop/) — grounded generation + optional light tool calls (file a ticket / open a request).
- [`../mcp-server/`](../mcp-server/) — clean boundary for the optional ticket/request tools (Ch 19).
- [`../eval-harness/`](../eval-harness/) — golden set **including "permission-probe" queries that must return nothing** (Ch 22).
- [`../observability-stack/`](../observability-stack/) — freshness monitoring so the corpus does not silently rot (Ch 30) + trace bad answers.

## Planned structure
```text
internal-knowledge-assistant/
├── README.md
├── PLAN.md
├── app/
│   ├── kb_assistant.py       # rag-pipeline + agent-loop, permission filter on query path
│   └── identity.py           # mock SSO: caller → allowed ACL groups (filter BEFORE retrieval)
├── ingest/
│   └── sync_acl.py           # carries per-doc access-control metadata into the index
├── evals/
│   └── permission_probes.jsonl  # queries that MUST return nothing + normal Q→A pairs
├── data/
│   └── corpus/               # ~10 docs tagged with ACL groups (one "comp sheet" = restricted)
└── demo.py                   # MOCK: same question, two identities → different results
```

## Maps to the book
- **Appendix G:** "Internal knowledge assistant / employee copilot" (permissioned RAG; buyer = any function).
- **Chapters showcased:** 13 (permissioned RAG), 26/41 (SSO identity + filter before model),
  22 (permission-probe evals), 30 (freshness monitoring), 25/38 (Slack/Teams/intranet surface),
  43 (enterprise RAG assistant).

## How to adapt it
- Point `ingest/sync_acl.py` at your real sources (wiki, drive, Slack export) and map their native ACLs.
- Replace `app/identity.py` with your SSO/IdP claims; keep the *filter-before-retrieval* rule intact.
- Surface it where people already work (Slack/Teams bot) instead of the demo CLI.
- Grow `evals/permission_probes.jsonl` to cover every sensitive corpus you index — this is the breach test.

## Phase-2 definition of done
- [ ] `demo.py` runs in MOCK mode; the restricted doc is invisible to the unprivileged identity.
- [ ] README frames problem → solution → pitch and links its Appendix-G section + chapters.
- [ ] Permission-probe evals are present and pass (return nothing); composes rag-pipeline + agent-loop without forking.
- [ ] Freshness/observability hook wired so a stale corpus is detectable.
