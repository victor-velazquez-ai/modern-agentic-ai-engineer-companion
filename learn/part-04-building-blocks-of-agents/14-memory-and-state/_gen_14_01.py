"""Generator for 14-01-context-budget-window-compaction.ipynb."""
import os

from _nbgen import Q3, code, md, write_nb

HERE = os.path.dirname(os.path.abspath(__file__))
cells = []

cells.append(md(r"""
# Short-term memory on a token budget

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 14 §14.1, §14.3, §14.4 · type: concept-lab*

**The promise:** by the end you can keep a long conversation inside a fixed token budget — pinning what must survive, windowing the recent turns, and compacting the rest — without losing the decisions that matter.
"""))

cells.append(md(r"""
## 🧠 Why this matters

The model only ever *sees* what fits in its context window on a given call. That window is large but finite, and it is more expensive and slower the more you fill it. So context is a **budget**, and memory engineering is budget management.

Picture the context window as a small **desk**. The model can only work with what is on the desk right now. Memory systems are the filing cabinets and sticky notes that decide what gets placed on the desk this moment and what gets filed away. Good memory is not "remember everything" — it is "have the right thing on the desk at the right time."

This notebook makes that tangible: you will watch a transcript blow the budget, then tame it with three moves — **pin**, **window**, **summarize (compact)**.
"""))

cells.append(md(r"""
## Objectives & prereqs

**By the end you can:**
- count a conversation's cost in *tokens*, not messages;
- build the book's `build_context()` sliding window (newest-first, token-budgeted);
- add a `compact()` step that summarizes what falls out of the window while preserving decisions, preferences, and open threads.

**Prereqs:** Ch 8 (tokenizers, "lost in the middle") · Ch 11 (model APIs for the summary call). No prior notebook required.

**Run first:** nothing — this notebook is offline-first and runs free in `MOCK=1` (the default).
"""))

cells.append(code(rf"""
# --- Setup ---------------------------------------------------------------
# Offline-first: everything below runs free with NO API key in MOCK mode.
import os
import random

from dotenv import load_dotenv

load_dotenv()  # reads a git-ignored .env if present; never hardcode keys

# MOCK=1 (default) -> canned, deterministic summaries. No network, no spend.
# MOCK=0 -> live summary call (Ch 11). Cost: ~1-2 short completions per compaction.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(14)  # deterministic synthetic transcript

# A real tokenizer if tiktoken is installed; a deterministic fallback otherwise.
# The fallback is intentionally crude (~4 chars/token) but STABLE, so the
# notebook teaches the same lesson on any machine.
try:
    import tiktoken

    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))

    _TOKENIZER = "tiktoken/cl100k_base"
except Exception:  # tiktoken not installed or no model data
    def count_tokens(text: str) -> int:
        # ~4 characters per token is a workable rule of thumb.
        return max(1, (len(text) + 3) // 4)

    _TOKENIZER = "fallback (~4 chars/token)"

print(f"MOCK        = {{MOCK}}")
print(f"tokenizer   = {{_TOKENIZER}}")
if not MOCK and not os.getenv("ANTHROPIC_API_KEY"):
    print("\n[!] MOCK=0 but ANTHROPIC_API_KEY is unset — the live summary call will fail.")
    print("    Set the key in .env, or just run with MOCK=1 (the default).")
"""))

cells.append(md(r"""
## A synthetic transcript

We generate a multi-turn conversation in-cell (seeded, so it is identical for everyone). A few turns carry real signal — a decision, a preference, an open task — buried among small talk. Then we paste in **one oversized log message**, the kind a user drops in the middle of a chat. That single message is what breaks naive memory.
"""))

cells.append(code(rf"""
# Build a seeded transcript: system prompt + alternating user/assistant turns.
SYSTEM = "You are a helpful project assistant. Be concise and remember decisions."

CHITCHAT = [
    "Thanks!", "Sounds good.", "Okay.", "Makes sense.", "Got it.",
    "Appreciate it.", "Cool.", "Right.", "Sure.", "Nice.",
]

SIGNAL = [
    ("user", "Decision: we ship the v2 API on Friday, not Monday."),
    ("user", "Preference: always give me metric units and a terse style."),
    ("user", "Open task: I still need the migration script reviewed."),
    ("assistant", "Noted: v2 ships Friday; metric + terse; migration review pending."),
]

messages = []
# Interleave a little chit-chat around the signal turns.
for i in range(6):
    messages.append({{"role": "user", "content": random.choice(CHITCHAT) + f" (turn {{i}})"}})
    messages.append({{"role": "assistant", "content": random.choice(CHITCHAT)}})
# Drop the signal turns in early — they are the start of the task.
for role, content in SIGNAL:
    messages.insert(random.randint(0, 6), {{"role": role, "content": content}})
# More recent chatter on top.
for i in range(6, 14):
    messages.append({{"role": "user", "content": random.choice(CHITCHAT) + f" (turn {{i}})"}})
    messages.append({{"role": "assistant", "content": random.choice(CHITCHAT)}})

print(f"{{len(messages)}} messages")
print(f"total tokens = {{sum(count_tokens(m['content']) for m in messages)}}")
"""))

cells.append(md(r"""
## The book's sliding window

The simplest real memory is a **sliding window**: keep the system prompt plus the most recent messages that fit the budget, newest-first, and drop the oldest. This is `build_context()` from §14.3 verbatim.
"""))

cells.append(code(rf"""
def build_context(system_prompt, messages, max_tokens, count_tokens):
    {Q3}Keep the system prompt + the most recent messages that fit the budget.{Q3}
    budget = max_tokens - count_tokens(system_prompt)
    kept = []
    for msg in reversed(messages):          # newest first
        cost = count_tokens(msg["content"])
        if cost > budget:
            break
        kept.append(msg)
        budget -= cost
    return [{{"role": "system", "content": system_prompt}}, *reversed(kept)]


BUDGET = 220  # a deliberately small budget so we can see eviction happen
ctx = build_context(SYSTEM, messages, BUDGET, count_tokens)
used = sum(count_tokens(m["content"]) for m in ctx)
print(f"kept {{len(ctx)}} / {{len(messages) + 1}} messages, {{used}}/{{BUDGET}} tokens")
print("oldest kept turn:", ctx[1]["content"][:60])
"""))

cells.append(md(r"""
## ⚠️ Pitfall: counting *messages* instead of *tokens*

A "keep the last 10 messages" window feels safe — until someone pastes a giant log. Messages vary wildly in size; a fixed message count silently **blows** the budget (one huge message) or **wastes** it (ten tiny ones). Budget in tokens, always, with the model's own tokenizer.

Let's drop one oversized message into the recent history and compare the two strategies.
"""))

cells.append(code(rf"""
# Someone pastes a 2,000-character log right before asking their question.
giant_log = "ERROR stacktrace line; " * 90  # ~2,000 chars
messages_with_log = messages + [
    {{"role": "user", "content": giant_log}},
    {{"role": "user", "content": "Given all that, what did we decide about the v2 API?"}},
]


def last_n_messages(system_prompt, messages, n=10):
    {Q3}The naive, buggy strategy: a fixed COUNT of recent messages.{Q3}
    return [{{"role": "system", "content": system_prompt}}, *messages[-n:]]


naive = last_n_messages(SYSTEM, messages_with_log, n=10)
naive_tokens = sum(count_tokens(m["content"]) for m in naive)

budgeted = build_context(SYSTEM, messages_with_log, BUDGET, count_tokens)
budgeted_tokens = sum(count_tokens(m["content"]) for m in budgeted)

print(f"last-10-messages window : {{naive_tokens:>5}} tokens  ({{len(naive)}} msgs)")
print(f"token-budgeted window   : {{budgeted_tokens:>5}} tokens  ({{len(budgeted)}} msgs)")
print(f"\nbudget was {{BUDGET}}. The message-count window overshoots by "
      f"{{naive_tokens - BUDGET}} tokens because of one pasted log.")
"""))

cells.append(md(r"""
🔮 **Predict — then run the next cell.** With the small budget and only pin + raw window (no summarization), do the early **signal** turns (the Friday-ship decision, the metric/terse preference, the open migration task) survive? Write down your guess before running.
"""))

cells.append(code(rf"""
# Which signal turns survived a raw token-budgeted window?
def survivors(ctx):
    kept = {{m["content"] for m in ctx}}
    return [content for _, content in SIGNAL if content in kept]


raw_ctx = build_context(SYSTEM, messages_with_log, BUDGET, count_tokens)
kept_signal = survivors(raw_ctx)

print("signal turns that survived the raw window:")
for content in (kept_signal or ["(none — they fell off the back of the desk)"]):
    print("  -", content[:70])
print(f"\n{{len(kept_signal)}}/{{len(SIGNAL)}} signal turns survived.")
print("The raw window forgets the START of the task — exactly what compaction fixes.")
"""))

cells.append(md(r"""
## The third move: `compact()`

A raw window is a blunt instrument — it forgets the start of a long task entirely. The fix is to **pin** the must-keep items, **window** the recent turns, and **summarize** what falls out so it is not lost. This is `compact()` from §14.4: summarize everything except the most recent turns into a running brief that preserves decisions, facts, preferences, and unfinished work.

In `MOCK=1` the summary is a deterministic, canned brief (no network). With `MOCK=0` it becomes a real model call.
"""))

cells.append(code(rf"""
def render(history):
    {Q3}Flatten a list of messages into text for the summarizer.{Q3}
    return "\n".join(f"{{m['role']}}: {{m['content']}}" for m in history)


def _mock_summary(old):
    {Q3}Deterministic stand-in for the LLM summary: pull out the salient turns.

    A real model would write prose; we extract the signal so the lesson —
    'decisions/preferences/open tasks survive compaction' — is reproducible.
    {Q3}
    salient = [m["content"] for m in old
               if m["content"] in {{c for _, c in SIGNAL}}]
    if not salient:
        return "Earlier small talk with no durable decisions."
    return "Decisions/preferences/open items so far: " + " | ".join(salient)


async def llm_summary(prompt, old):
    if MOCK:
        return _mock_summary(old)
    # Live path (Ch 11): one short Anthropic call. Costs ~1-2 cents.
    from anthropic import Anthropic

    client = Anthropic()  # reads ANTHROPIC_API_KEY from env
    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=256,
        messages=[{{"role": "user", "content": prompt + "\n\n" + render(old)}}],
    )
    return resp.content[0].text


async def compact(history, keep_recent=6):
    {Q3}Summarize everything except the most recent turns into a running brief.{Q3}
    old, recent = history[:-keep_recent], history[-keep_recent:]
    if not old:
        return history
    brief = await llm_summary(
        "Summarize the conversation so far. Preserve decisions made, facts "
        "established, user preferences, and any unfinished tasks. Be terse and factual.",
        old,
    )
    return [{{"role": "system", "content": f"Summary so far:\n{{brief}}"}}, *recent]
"""))

cells.append(code(rf"""
# Compact the full transcript, then build the window on the compacted history.
compacted = await compact(messages_with_log, keep_recent=6)

print("--- the running brief (pinned at the top) ---")
print(compacted[0]["content"])
print("\n--- recent turns kept verbatim ---")
for m in compacted[1:]:
    print(f"  {{m['role']}}: {{m['content'][:60]}}")

after = build_context(SYSTEM, compacted, BUDGET, count_tokens)
after_tokens = sum(count_tokens(m["content"]) for m in after)
print(f"\ncompacted context: {{after_tokens}}/{{BUDGET}} tokens, "
      f"and the v2/metric/migration facts are preserved in the brief.")
"""))

cells.append(md(r"""
## Recursion: summaries of summaries

A long session keeps growing. Compaction is **recursive**: when the compacted history *itself* overflows, summarize its old span again, so the running brief stays bounded no matter how long the session runs. Trigger on a threshold (e.g. 70% of budget), not every turn, to control cost.
"""))

cells.append(code(rf"""
# Simulate a very long session: keep appending turns and compact on a threshold.
async def run_long_session(turns, budget, keep_recent=6, threshold=0.7):
    history = [{{"role": "system", "content": SYSTEM}}]
    compactions = 0
    for i in range(turns):
        history.append({{"role": "user", "content": f"step {{i}}: small update, all routine."}})
        if sum(count_tokens(m["content"]) for m in history) > budget * threshold:
            history = await compact(history, keep_recent=keep_recent)
            compactions += 1
    return history, compactions


history, n = await run_long_session(turns=80, budget=BUDGET)
final_tokens = sum(count_tokens(m["content"]) for m in history)
print(f"ran 80 turns, compacted {{n}} times")
print(f"final context stayed at {{final_tokens}} tokens (budget {{BUDGET}}) — bounded, not growing.")
"""))

cells.append(md(r"""
## 🎯 Senior lens: salience, not size

The hard question in compaction is not *how much* to keep — it is *what*. A senior optimizes for **salience**:

- **Must survive:** commitments and decisions, user preferences, stable identifiers, and unfinished work. Losing "ships Friday" or "allergic to penicillin" is a bug, not a saving.
- **Safe to drop:** pleasantries, acknowledgements, and superseded intermediate steps that a later turn already overwrote.

And **when** to compact is a cost lever: trigger on a budget threshold (say 70%), not on every turn — each compaction is a model call. The goal is *relevant, minimal* context, not maximal context. "Just use a bigger window" doesn't escape this: cost and latency still grow with tokens, and models attend unevenly to very long inputs (the "lost in the middle" effect from Ch 8).
"""))

cells.append(md(r"""
## Recap

- The context window is a **scarce budget**; memory engineering is budget management.
- **Budget in tokens, never messages** — one pasted log breaks a message-count window.
- `build_context()` keeps the system prompt + the most recent turns that fit (pin + window).
- A raw window forgets the *start* of a task; `compact()` summarizes what falls out, preserving decisions, preferences, and open threads.
- Compaction is **recursive** and **threshold-triggered**, so a long session stays bounded at controlled cost.
"""))

cells.append(md(r"""
## Exercises

Each exercise *changes* something and asks you to predict the result first. (Solutions live in `solutions/`, not inline.)

1. **Pin explicitly.** Add a `pinned` list (system prompt + current goal + "metric/terse") that `build_context()` always keeps *before* windowing. Predict: at `BUDGET = 120`, how many recent turns still fit?
2. **Tune `keep_recent`.** Re-run `run_long_session` with `keep_recent=2` and `keep_recent=12`. Predict which compacts *more often* and which keeps a *longer* verbatim tail — then confirm.
3. **Swap the tokenizer.** Force the fallback counter (rename the `tiktoken` import) and compare `build_context` decisions to the real tokenizer on the giant-log message. Where do they disagree, and why does that matter for budgeting?
4. **Salience test.** Add a fake "allergic to penicillin" turn near the start. Does your `_mock_summary` preserve it through three compactions? If not, fix the salience rule.
"""))

cells.append(code(r"""
# Exercise 1 — pin essentials before windowing.
"""))

cells.append(code(r"""
# Exercise 2 — vary keep_recent and compare compaction frequency.
"""))

cells.append(code(r"""
# Exercise 3 — swap tokenizers and find where budgeting decisions diverge.
"""))

cells.append(code(r"""
# Exercise 4 — verify a critical fact survives repeated compaction.
"""))

cells.append(md(r"""
## Next

- **Next notebook:** [`14-02-long-term-memory-recall-reflection.ipynb`](./14-02-long-term-memory-recall-reflection.ipynb) — the chapter's 🔧 **Build**: a layered `Memory` class with ranked long-term recall and reflective writes. Short-term compaction (this notebook) becomes its `remember_turn` path.
- **Blueprint:** [`../../../blueprints/memory-module/`](../../../blueprints/memory-module/) — the production layered memory behind a clean interface.
- **Capstone:** advances `capstone/memory/` (checkpoint `checkpoints/ch14-memory`).
"""))

out = write_nb(os.path.join(HERE, "14-01-context-budget-window-compaction.ipynb"), cells)
print("wrote", out)
