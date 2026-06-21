# Internal Knowledge Assistant / Employee Copilot

> **Solution blueprint** · Appendix G use case #2 · *composes pattern blueprints; does not fork them*
>
> A permissioned employee copilot that answers from the company's own knowledge — grounded,
> cited, and **identity-aware by construction**. Runs **free and offline** in MOCK mode (the
> default): no API keys, no spend.

---

## Problem

Institutional knowledge is technically written down but practically unfindable, so the real
interface to it ends up being *interrupting a senior person*. Almost every function buys some
version of an internal assistant (IT, HR, ops, finance, engineering onboarding) to recover that
time on both sides and to cut the policy-violation mistakes people make out of ignorance.

The thing that makes this category hard — and the thing most demos quietly skip — is
**permissions**. An employee must never retrieve content their identity cannot already access.
A comp sheet, an unreleased financial, a restricted runbook: the assistant has to be *more*
careful than a shared drive, not less, because it actively goes and fetches the most relevant
material and puts it in front of the user.

## Solution

An assistant that, for each question:

1. **resolves the caller's identity → ACL groups** (mock SSO; swap for your IdP),
2. **filters the corpus to readable chunks _before_ retrieval ever runs** (the load-bearing rule),
3. **hybrid-retrieves + reranks** over only those permitted chunks, and answers with **inline
   citations** — or honestly abstains when nothing readable matches,
4. optionally **files a ticket** through a guarded tool when it can't answer, and
5. is **traceable** and **freshness-monitored** so bad answers are debuggable and a stale corpus
   is detectable.

### The one rule: filter *before* retrieval

```
identity ─▶ filter store to readable chunks ─▶ hybrid retrieve ─▶ rerank
                                                                   │
                                            ground answer + cite ◀─┘   (or: escalate → file ticket)
```

Filtering *after* retrieval — or, worse, asking the model "please don't quote the restricted
doc" — is a breach waiting to happen: the moment a forbidden chunk is in the prompt it can leak
through a paraphrase, a summary, or a jailbreak. Here a forbidden chunk is **never in the
candidate set**, so it cannot reach the prompt, the citations, or the model. The breach is
impossible by construction, not by hoping the model behaves. See
[`app/kb_assistant.py`](app/kb_assistant.py) → `permissioned_store`.

### What it composes (pattern blueprints — by relative import, never forked)

| Pattern blueprint | Role here | Wired in |
|---|---|---|
| [`../rag-pipeline/`](../rag-pipeline/) | Permissioned hybrid retrieval + reranking + citations; ACL rides on chunk metadata | `ingest/sync_acl.py`, `app/kb_assistant.py` |
| [`../agent-loop/`](../agent-loop/) | Grounded generation + optional light tool call (file a ticket) | `app/kb_assistant.py` → `escalate()` |
| [`../mcp-server/`](../mcp-server/) | Clean, least-privilege boundary for the ticket tool (allow-list + schema + timeout) | `app/ticket_tool.py` |
| [`../eval-harness/`](../eval-harness/) | Golden set incl. **permission-probe** cases that must return nothing | `evals/run_evals.py` |
| [`../observability-stack/`](../observability-stack/) | Per-question trace tree + corpus **freshness** monitoring | `app/kb_assistant.py`, `app/freshness.py` |

The pattern blueprints are added to `sys.path` from their sibling `src/` dirs and imported; this
solution adds only the *permission* layer (identity, ACL ingest, filter) and the wiring.

## Run it

```bash
cd blueprints/internal-knowledge-assistant
python demo.py            # MOCK mode is the default — no keys, no spend
python evals/run_evals.py # the breach test + grounded-answer gate (exits non-zero on regression)
```

`demo.py` shows the headline result: **the same restricted question returns different evidence
for different identities.**

- As **Alice** (regular employee): the comp sheet is invisible — 10 visible docs, no
  `compensation-sheet` citation, the secret codename never appears.
- As **Dana** (finance leadership): the same question surfaces and cites the comp sheet — 11
  visible docs.

It then shows a normal grounded answer, an **agent-loop escalation** that files a ticket through
the **MCP-guarded** `file_ticket` tool, an **observability** trace of one answer, and a
**freshness** report (the deliberately old `code-of-conduct.md` is flagged stale).

`evals/run_evals.py` is the CI gate. The `permission-probe` cases assert the restricted doc never
reaches an unprivileged caller's citations (a breach is a hard fail); the `authorized` case
asserts finance leadership *can* still read it (the gate is access control, not blanket
suppression); the `answerable` cases assert the assistant actually grounds its answers.

## Files

```text
internal-knowledge-assistant/
├── README.md                    # this file
├── PLAN.md                      # the spec (unchanged)
├── demo.py                      # MOCK: same question, two identities → different results
├── app/
│   ├── identity.py              # mock SSO: caller → allowed ACL groups (the IdP seam)
│   ├── kb_assistant.py          # composes rag-pipeline + agent-loop + observability; filter-before-retrieval
│   ├── ticket_tool.py           # the file-a-ticket tool over a guarded MCP boundary
│   └── freshness.py             # corpus freshness monitor (so the KB doesn't silently rot)
├── ingest/
│   └── sync_acl.py              # carries each doc's ACL groups into the index at ingest time
├── evals/
│   ├── permission_probes.jsonl  # must-return-nothing probes + normal Q→A + an authorized case
│   └── run_evals.py             # runs the set through eval-harness; non-zero exit on regression
└── data/
    └── corpus/                  # 11 docs + acl.json sidecar (one restricted "comp sheet")
```

## Live path (opt in — costs money)

Everything above is MOCK (`COMPANION_MOCK=1`, the default): a deterministic hash embedder, a
heuristic reranker, an extractive "model", and an in-process MCP server. To go live:

- `export COMPANION_MOCK=0` and provide your provider key in the environment (e.g.
  `ANTHROPIC_API_KEY`). **Secrets come from env — none are committed.**
- The `rag-pipeline` embedder and the `agent-loop` model port both fall back to the mock unless a
  gateway-backed implementation is on the path; wire the [`../llm-gateway/`](../llm-gateway/)
  blueprint in to get real embeddings and generation. The composition does not change — only the
  ports behind the seams do.

## How to adapt it to *your* domain

1. **Point ingestion at your real sources.** Edit [`ingest/sync_acl.py`](ingest/sync_acl.py) →
   `load_corpus` to read your wiki / drive / Slack export, and **map each source's native ACLs**
   onto the `acl` group set (a wiki space's read group, a drive folder's sharing groups, a Slack
   channel's membership). The contract: every document arrives with a non-empty set of group
   names, and those names match what identity resolves callers to.
2. **Replace identity with your SSO/IdP.** Swap [`app/identity.py`](app/identity.py)'s in-memory
   directory for an adapter over your OIDC/SAML claims (Okta/Entra groups, an LDAP lookup). Keep
   the *filter-before-retrieval* rule intact — that is the whole security model.
3. **Grow the permission probes.** Add a `permission-probe` case to
   [`evals/permission_probes.jsonl`](evals/permission_probes.jsonl) for **every sensitive corpus
   you index**. This is your breach test; it should fail loudly the day a misconfigured ACL would
   leak something. Run it in CI.
4. **Surface it where people work.** Replace the demo CLI with a Slack/Teams bot or an intranet
   widget. The assistant API (`KnowledgeAssistant.ask(question, principal)`) does not change.
5. **Wire freshness into a monitor.** Run [`app/freshness.py`](app/freshness.py)'s
   `check_freshness` on a nightly schedule against `date.today()` and alert on the stale set, so
   the corpus can't quietly rot under confident answers.

## Maps to the book

- **Appendix G:** "Internal knowledge assistant / employee copilot" (permissioned RAG; buyer =
  any function).
- **Chapters showcased:** 13 (permissioned RAG), 26/41 (SSO identity + filter before the model),
  19 (MCP tool boundary), 12 (agent loop / tool use), 22 (permission-probe evals), 23/30
  (tracing + freshness monitoring), 43 (enterprise RAG assistant).

> **Pedagogy note.** Like every blueprint, this is a *study-and-adapt* reference, not an
> answer key to clone. The capstone you build yourself; this shows how a senior would structure
> the permissioned-assistant composition so you can lift the ideas into your own system.
