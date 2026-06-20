# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2025-01-01   **Deciders:** Engineering team

## Context

As a system grows, the *reasoning* behind its architecture lives only in the heads of the
people who were in the room — and those people leave, forget, or disagree later about what was
actually decided. New contributors re-litigate settled questions because the trade-offs were
never written down, and reviewers can't tell an intentional choice from an accident. Commit
messages and chat threads are too scattered and too ephemeral to serve as the durable record.
We need a lightweight, low-friction way to capture the *why* of significant, hard-to-reverse
decisions at the moment we make them — friction low enough that the team will actually keep
doing it.

## Decision

We will record significant architectural decisions as **Architecture Decision Records (ADRs)**
— short Markdown files kept in `docs/adr/`, one decision per file, using the four-section
Nygard format (Context · Decision · Alternatives considered · Consequences). ADRs are numbered
sequentially (`NNNN-kebab-title.md`), are **immutable** once Accepted (a reversal is a new ADR
that supersedes the old one), and are committed **alongside the change they describe**.

## Alternatives considered

- **No formal record (rely on commit messages / chat / tribal knowledge)** — Rejected: the
  status quo that created the problem. Commit messages explain *what* changed, rarely *why*,
  and are nearly impossible to browse as a coherent decision history.
- **A single growing `DECISIONS.md` file** — Rejected: a monolith produces constant merge
  conflicts, has no natural unit to review per-decision, and grows into an unsearchable wall of
  text with no clear supersession story.
- **A wiki or external tool (Confluence, Notion)** — Rejected: decisions then live outside the
  repo, drift from the code, aren't versioned with it, and require a login to read. Keeping
  ADRs in-repo means they're reviewed, diffed, and time-traveled exactly like the code.
- **A heavier template (full RFC with stakeholders, risk matrix, sign-offs)** — Rejected: too
  much ceremony. The whole point is friction low enough that people keep writing them; four
  sections is the sweet spot.

## Consequences

- **Positive:** New contributors can read `docs/adr/` and understand *why* the system is the
  way it is. Settled debates stay settled. Decisions are reviewed in PRs like any other change,
  and the log doubles as portfolio/architecture evidence.
- **Negative:** Writing an ADR takes a few minutes of discipline at decision time, and the team
  has to agree on what's "significant enough" to warrant one (the bar: hard to reverse).
- **Follow-on:** Keep [`README.md`](README.md) updated as the index. Establish the norm in code
  review that decisions which are expensive to reverse arrive *with* an ADR. Supersede, never
  edit, when a decision changes.
