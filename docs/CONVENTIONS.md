# Conventions

Naming, structure, and the canonical `PLAN.md` template. Following these keeps the repo
navigable and makes it read as one product with the book.

---

## Folder & file naming

- **kebab-case** everywhere for folders.
- **Chapters keep the book's exact numbering and slug:** `chapters-companion/ch12-tool-use-and-function-calling/`.
- **Parts** are `part-NN-short-slug` where `NN` is the part's position (01–13).
- **Notebooks:** `NN-MM-short-title.ipynb`
  - `NN` = chapter number (zero-padded), `MM` = order within the chapter (`01`, `02`, …).
  - Example: `12-01-tool-loop-from-scratch.ipynb`, `12-02-parallel-tools-and-recovery.ipynb`.
- **Blueprints/templates:** `kebab-case` topic folder (`rag-pipeline/`, `fastapi-agent-service/`).
- **Supporting files** inside a chapter folder: `data/` (fixtures), `solutions/` (exercise
  solutions, Phase 2), `img/` (any static diagrams). Keep notebooks at the folder root.

---

## Callout grammar (mirror the book)

Use the same emoji vocabulary the book uses, in notebook markdown cells, so the two feel
unified:

| Emoji | Meaning | Use in notebooks for… |
|---|---|---|
| 🧠 | Mental model | the intuition/diagram cell before the mechanics |
| 🔧 | Build | a cell that builds a real, runnable piece |
| ⚠️ | Pitfall | a cell that shows a common mistake and the fix |
| 🎯 | Senior/Architect lens | a cell on how a senior reasons about the trade-off |
| 📋 | Checklist | a production-readiness checklist cell |
| 📓 | Companion pointer | (in the **book**) a pointer to a notebook/asset here |
| 🔮 | Predict | "predict the output before you run the next cell" prompts |

---

## Cross-referencing

- Notebooks link to the **book** by chapter/section number: "see §12.4."
- Notebooks link to **blueprints/templates** by relative path so they resolve on GitHub and
  locally: `../../../blueprints/agent-loop/`.
- A walkthrough notebook should **end by pointing at the blueprint** that contains the
  production version of what it just built ("you built the toy; here's the real one").

---

## The canonical `PLAN.md` template

**Every chapter and asset folder uses this exact skeleton in Phase 1.** It is the unit of
planning: precise enough that Phase 2 can be executed from it without re-deriving intent.
Keep it tight — bullets over paragraphs.

```markdown
# Ch NN — <Chapter Title>

> Companion plan · Part <P> · book file `chapters/NN-<slug>.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
<1–3 sentences: what running these assets adds beyond reading the chapter. If this is a
reference/worksheet-only chapter, say so and why.>

## Planned notebooks
<!-- repeat this block per notebook; omit the section entirely for no-code chapters -->
### NN-MM · `<notebook-file>.ipynb` — <title>
- **Type:** concept-lab | walkthrough | drill | worksheet
- **Maps to:** book §NN.x (note 🔧 Build sections explicitly)
- **Objective:** <the one thing the reader can do after this>
- **Prereqs:** <chapters/notebooks/tools needed first>
- **Cell arc:** <5–10 bullets — the notebook's sections, in order, including a 🔮 predict
  moment and a ⚠️ pitfall>
- **Datasets/fixtures:** <what data; tiny + committed, or generated>
- **APIs & cost:** <none/offline | mockable | live-API; rough token budget>
- **You'll be able to:** <2–3 concrete outcomes>

## Feeds (cross-pillar)
- **Blueprint(s):** <blueprints/... this chapter contributes to, or "—">
- **Template(s):** <templates/... or "—">
- **Capstone:** <capstone dir / checkpoint this advances, per Appendix C, or "—">

## Dependencies
- <prior chapters/blueprints that must exist first>

## Phase-2 definition of done
- [ ] Each notebook runs top-to-bottom (mock mode) with no errors.
- [ ] Matches the book's terminology, code shapes, and pitfalls for this chapter.
- [ ] Recap + exercises present; secrets read from env only.
- [ ] Cross-links to blueprint/template/capstone resolve.
```

---

## What Phase 1 does **not** include

- No `.ipynb` files, no implementation code, no real blueprint/template/capstone source.
- `PLAN.md` files only (plus the part `README.md` and the top-level docs). The plan is the
  deliverable; the build is Phase 2.
