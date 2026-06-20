# Book Integration — wiring the companion into the 2nd (master) edition

This repo and the book ship as one product. The book's **2nd edition is the master edition**:
the first to reference the companion throughout. This document is the plan for that
republish — the narrative reconciliation, every exact edit point, the version-pinning scheme,
and the KDP checklist.

> **Sequence (do not reorder):** finish & test the repo (Phase 2) → *then* edit the book
> (Phase 3) → rebuild → QA → republish. The book must only ever point at assets that exist
> and run.

---

## 1. The narrative problem (and the fix)

The 1st edition tells the reader, in two prominent places, that **there is no repo to clone**:

- **Ch 2 (How to Use This Book):** "There is no repo to clone — you write it yourself, one
  Build section at a time… Appendix C is the map of that finished structure; you are building
  toward it, not from it."
- **Appendix C (The Capstone Repository):** "The capstone… is not a repo you download; it is
  the repo *you* build… Treat it as the blueprint you are working toward, not a starting point
  to clone."

We are now shipping a companion that **includes** a complete, clonable capstone. Left
unaddressed, that's a direct contradiction. The fix is **not** to retreat from "build it
yourself" — that promise is the book's pedagogical core. The fix is to reframe the companion
as the thing that makes building-it-yourself *safer and richer*:

> **New framing (use this voice consistently):** "You still build the capstone yourself —
> that's where the learning is. The companion repository is your **lab, your reference, and
> your safety net**: run the ideas as notebooks, study production-grade blueprints, start new
> work from templates, and when a Build section leaves you stuck, diff your code against the
> matching **checkpoint** instead of giving up. Build first; compare second."

This turns a contradiction into a selling point: the book is now a *book + lab + reference +
course*.

---

## 2. Exact edit points in the book

Paths are relative to `books/modern-agentic-ai-engineer/`.

### 2.1 New callout in `style.typ`
- Add a **`#companion[...]`** callout box (icon 📓, accent border) — the in-book pointer to a
  notebook/blueprint/template/checkpoint. One visual, used everywhere, so readers learn to
  recognize "there's a runnable version of this."
- Register it like the existing callouts (`build`, `pitfall`, etc.). Keep the palette.

### 2.2 `chapters/02-how-to-use-this-book.typ`
- **Rewrite** the "There is no repo to clone" paragraph to the new framing (§1).
- **Add a section "== The companion repository"**: the four pillars (learn / blueprints /
  templates / capstone), the clone URL + pinned release tag, the `MOCK=1` cost-free mode, and
  the "build first, compare second" rule. Cross-reference Appendix C.
- Update the reading-paths text to mention running the notebooks alongside each part.

### 2.3 `chapters/92-appendix-capstone.typ` (Appendix C)
- **Reframe the opening**: keep "the repo you build," add "…and a complete reference
  implementation now lives in the companion at `capstone/`, with per-Build `checkpoints/` so
  you can check your work."
- Update the `git clone …agentic-platform.git` example to the companion URL and the
  `capstone/` path; keep the "your own remote" note for the reader's *own* build.
- Add a short "How to use the reference without cheating yourself" box.

### 2.4 Every 🔧 Build section (all chapters with one)
- Append a `#companion[...]` callout: the **notebook** that builds the toy version, the
  **blueprint** with the production version, and the **checkpoint** to diff against. Use the
  chapter→asset map in [`REPO-PLAN.md`](REPO-PLAN.md) §4 to fill these in.
- Inventory of Build sections to annotate: §12.4, 13.7, 14.10, 17.5, 18.7, 19.3, 20.4, 22.7,
  25.5, 31.8, 33.10, 36.4, 38.5, 42.7 (+ any added in editing). Confirm by grepping the
  source for the `#build[` opener before the pass.

### 2.5 Front matter / preface
- Add a short **"Companion repository"** note near the front (after the title page or in the
  preface): one paragraph + the URL + the pinned tag, so a reader knows on day one.

### 2.6 Appendices A, B, D
- **A (toolchain):** point readers to the repo's `docs/SETUP.md` and `.env.example` as the
  living, tested setup; keep the book's summary.
- **B (cheat sheets):** note that runnable versions live in the companion.
- **D (resources):** add the companion repo as the first entry.

### 2.7 Marketing surfaces (not the interior)
- **`LISTING.md`** description: add a line — *"Includes a full open-source companion: 100+
  runnable notebooks, professional blueprints, work-ready templates, and the complete
  capstone — every chapter, hands-on."* Consider a keyword nudge ("Jupyter notebooks").
- **Back-cover blurb** (print cover source): one line announcing the companion.
- Subtitle/ title: **leave unchanged** (avoid re-branding a selling title).

---

## 3. Version pinning (book edition ↔ repo release)

A printed book is frozen; the repo moves. Prevent drift:

- **Tag the repo to each edition.** Book 2nd edition ↔ repo **`v2.0.0`**. The book prints the
  URL **and the tag**: "pinned to release `v2.0.0`; `git checkout v2.0.0` for the exact code
  in this edition; `main` for the latest."
- Maintain a compatibility table here:

  | Book edition | Repo tag | Notes |
  |---|---|---|
  | 1st (published) | — | no companion |
  | 2nd (master) | `v2.0.0` | first edition with the companion |

- **Pin dependencies** (`requirements.txt`, lockfiles) at each tag so old editions stay
  runnable.
- Keep a repo `CHANGELOG.md` entry per tagged release.

---

## 4. Republish checklist (Phase 3)

Follows `docs/PUBLISHING-KDP.md` and `CLAUDE.md`. Do **after** the repo is built and tested.

- [ ] Repo Phase 2 complete: all notebooks run green in CI; capstone smoke test passes; repo
      tagged `v2.0.0`; deps pinned.
- [ ] Add `#companion[...]` callout to `style.typ`; verify it renders.
- [ ] Apply all §2 edits; **grep every "Chapter N" / "§N.x"** for staleness after edits.
- [ ] `npm run build -- --book modern-agentic-ai-engineer` → note new page count (`pypdf`).
- [ ] **Recompute spine** = `pages × 0.002252`; **regenerate the print cover**; add the
      companion line to the back cover.
- [ ] `npm run epub` → **`epubcheck` 0 errors**; `pdffonts` shows every font embedded.
- [ ] Render cover, TOC, a part divider, a Build page with the new 📓 callout, and Appendix C
      to PNG and **eyeball** them.
- [ ] Update **KDP**: upload new interior PDF + cover to the **same title** (preserves the
      book's reviews); update the description/keywords from `LISTING.md`; keep the **AI-use
      disclosure** truthful.
- [ ] Decide ISBN: a free KDP paperback ISBN for a new edition if required; record it in
      `LISTING.md`. Kindle updates in place (same ASIN).
- [ ] Make the repo **public** at launch (if it was private) and flip the README status from
      "planning skeleton" to "live"; announce.
- [ ] Update `LISTING.md`, the book `CHANGELOG.md`, and `OUTLINE.md` progress note.

---

## 5. Open decisions for the author (flag at Phase 3)

- **Per-Build callout density:** a 📓 callout on *every* Build section, or only the major
  ones? (Default: every Build section — consistency teaches the habit.)
- **Checkpoint depth:** a checkpoint per Build section (≈14) vs per part (≈8)? (Default: per
  Build section — finer is more useful when stuck.)
- **Capstone "answer key" wording:** how strongly to discourage clone-and-run vs
  build-then-compare. (Default: firm but friendly; repeat the rule at each pointer.)
