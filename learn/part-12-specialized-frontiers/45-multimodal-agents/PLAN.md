# Ch 45 — Multimodal Agents

> Companion plan · Part XII · book file `chapters/45-multimodal-agents.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Reading teaches that "multimodality is a new set of adapters at the edges, not a new core";
running it makes that real. The notebooks wire image/document inputs into the *same* agent
loop from Part IV and — crucially — build the **verification gate** that separates demo-grade
extraction from production-grade. The reader leaves having extracted structured JSON from a
scanned document *and* caught the model's plausible-but-wrong field with their own code.

## Planned notebooks

### 45-01 · `45-01-modalities-as-adapters.ipynb` — Every modality, two questions
- **Type:** concept-lab
- **Maps to:** book §45.2 (🧠 *mentalmodel*: how it becomes context / which tool produces it),
  §45.1 (vision/document inputs), §45.2 (audio-as-ingestion, image-generation-as-output-tool)
- **Objective:** classify any modality by the two questions the chapter poses — *how does it
  become context* (image/audio/transcript in) and *which tool produces it* (TTS/image-gen out)
  — and see that the agent loop, memory, and orchestration don't change.
- **Prereqs:** Ch 11 (model APIs, content-block shapes); Ch 12 (the tool-use loop).
- **Cell arc:**
  - 🧠 the adapter diagram: a vision/audio/image-gen edge bolted onto the unchanged Part IV loop.
  - Build an image content-block and an audio-transcript "document loader"; inspect both shapes.
  - Register a *mock* `generate_image(prompt, size, style)` tool — output modality = just a tool.
  - 🔮 *predict* which parts of the loop change when you add vision (answer: only the edges).
  - Run one fully-mocked multimodal turn (image in → reason → image-gen tool out) and trace it.
  - ⚠️ pitfall: treating "the model can see" as a new architecture — it's a new input *type*.
  - 🎯 senior lens: *where to spend the quality budget* — vision-extraction replaces OCR
    contracts (durable value); generated media is cheap to make, expensive to review.
- **Datasets/fixtures:** one tiny sample image and a 3-line mock transcript in `data/` (committed).
- **APIs & cost:** none — fully offline/mock by design (canned vision + image-gen responses).
- **You'll be able to:** place any modality on the "context-in / tool-out" map and explain why
  the core loop is untouched.

### 45-02 · `45-02-document-extraction-pipeline.ipynb` — 🔧 OCR-grade extraction *with verification*
- **Type:** walkthrough  *(builds the chapter's production pattern)*
- **Maps to:** §45.1 (🔧 document understanding), §45.1 (#keyidea: extraction = pipeline with
  verification), §45.1 (#pitfall: models fail *plausibly*; #pitfall: images are an injection
  surface; #tip: build a labeled eval set first)
- **Objective:** turn a document image/PDF into validated JSON, gating the model's output with
  a schema + arithmetic cross-check + a confidence threshold that routes failures to a queue.
- **Prereqs:** 45-01; Ch 13 (retrieval, for the "don't ship 50 pages into context" alternative);
  Ch 15 (schema-first validation / repair) reused here verbatim.
- **Cell arc:**
  - 🧠 "the model is the extractor; *your code* is the quality gate" — the chapter's central move.
  - Send a (mock) invoice image with a Pydantic schema; ask for `null` on low-confidence fields.
  - Validate against the schema; cross-check arithmetic (do line items sum to the total?).
  - 🔮 *predict* whether a deliberately blurred-digit fixture passes — then watch the gate catch it.
  - Route low-confidence / failed-validation docs to a mock human-review queue (the review boundary).
  - ⚠️ pitfall: a transposed digit returns *confident and well-formatted* — demand verbatim
    transcription + checksums for high-stakes fields (amounts, IDs, dates).
  - ⚠️ pitfall: an instruction painted into the image (indirect prompt injection) — treat every
    pixel as untrusted content; extend Ch 41's defenses to this modality.
  - 📋 a tiny labeled eval set (≈5 docs, ground-truth fields) scoring field-level accuracy —
    Part VI discipline applied to pixels.
  - 🎯 senior lens: resolution/DPI and image-token cost beat prompt cleverness; tile dense pages.
- **Datasets/fixtures:** 4–5 tiny synthetic "documents" in `data/` (a clean invoice, a
  blurred-digit variant, an injection-laced image, a multi-line table) + a `ground_truth.json`.
- **APIs & cost:** mockable (`MOCK=1` returns canned extraction blocks incl. the wrong-digit
  case); live ≈ a handful of vision calls — note that a page image ≈ several thousand text tokens.
- **You'll be able to:** ship a verified extraction pipeline and *measure* its field-level
  accuracy instead of hoping for it.

## Feeds (cross-pillar)
- **Blueprint(s):** — (no standalone blueprint; the verify→repair→route pattern reuses
  [`blueprints/eval-harness/`](../../../blueprints/eval-harness/) discipline and Ch 15's
  structured-output choke point).
- **Template(s):** —
- **Capstone:** — (no dedicated capstone module; multimodal inputs are an optional adapter on
  the existing agent loop. Notebook closes by noting where a `vision`/`extract` tool would plug
  into `capstone/agents/tools/`.)

## Dependencies
- Ch 11 (model APIs / content blocks) · Ch 12 (tool loop) · Ch 13 (retrieval alternative) ·
  Ch 15 (schema validation + repair) · Ch 41 (injection defenses) · Ch 22 (eval discipline).

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` with no errors and no network.
- [ ] Extraction uses a Pydantic schema + arithmetic cross-check + human-queue routing, matching
      §45.1's "pipeline with verification" framing and pitfalls (plausible failure, injection).
- [ ] The field-level eval cell reports accuracy against committed ground truth.
- [ ] Recap + 2–4 exercises (e.g., add a checksum field; raise DPI and re-measure); secrets from env.
