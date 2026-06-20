# Ch 34 — Azure & GCP for AI

> Companion plan · Part VIII · book file `chapters/34-azure-and-gcp.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This chapter's whole thesis is that a second cloud is *translation, not relearning* — so the
companion gives one **concept lab** about parity and portability, not a tour of three consoles.
The reader runs a tiny "translate the architecture" exercise (AWS → Azure → GCP across the four
primitives) and, more importantly, *feels* the portability discipline by swapping a
cloud-specific provider behind a stable interface and watching the app not care. No real Azure
or GCP account, no spend — the point is the mental map and the hexagonal seam, both offline.

## Planned notebooks

### 34-01 · `34-01-parity-and-portability.ipynb` — Translate the cloud, then prove portability
- **Type:** concept-lab
- **Maps to:** §34.1 (Azure for AI), §34.2 (GCP for AI), §34.3 (multi-cloud & portability strategy)
- **Objective:** translate an AWS architecture into Azure and GCP equivalents by primitive, and
  demonstrate "portability without multi-cloud" by swapping a provider behind one interface.
- **Prereqs:** Ch 32 (four primitives); Ch 28 (hexagonal/ports-and-adapters) for the seam;
  Ch 33 as the AWS baseline being translated.
- **Cell arc:**
  - 🧠 mental model: same four primitives, different names — AWS ↔ Azure ↔ GCP service table.
  - A `translate(service, target_cloud)` drill over the capstone's components — 🔮 *predict* the
    Azure/GCP name (Fargate→Container Apps/Cloud Run, S3→Blob/Cloud Storage, IAM→Entra ID/IAM…),
    then check a tiny committed mapping table.
  - The model-access angle: Azure OpenAI (GPT, enterprise/compliance boundary) vs Bedrock (Ch 33,
    Claude) vs Vertex AI (Gemini, data/ML gravity) — a comparison cell, not live calls.
  - 🔧 portability seam: define one `ObjectStore` port; provide two *fake* in-memory adapters
    ("s3-like", "blob-like"); run the same app logic through each and assert identical behavior.
  - 🔮 *predict* what has to change in business logic when you swap adapters (answer: nothing).
  - ⚠️ pitfall: chasing real multi-cloud — show the cost (doubled ops, diluted depth, forfeited
    managed services) vs the cheaper "portable but single-cloud" middle path (§34.3 senior lens).
  - 🎯 senior lens: go deep on one cloud; keep domain logic cloud-agnostic behind interfaces;
    reserve true multi-cloud for genuine regulatory/resilience mandates.
- **Datasets/fixtures:** a tiny committed `data/cloud-parity.json` (concept → AWS/Azure/GCP names).
- **APIs & cost:** none — fully offline by design. No Azure/GCP/AWS account; the adapters are
  in-memory fakes, so there is **no spend** and no live-API path.
- **You'll be able to:** map any AWS design onto Azure/GCP on sight, and structure code so
  switching clouds is feasible without paying the daily multi-cloud tax.

## Feeds (cross-pillar)
- **Blueprint(s):** — (the ports-and-adapters seam echoes the hexagonal structure used across
  `blueprints/`; no new blueprint).
- **Template(s):** — (reinforces the portability discipline templates already bake in; no
  cloud-specific template).
- **Capstone:** no new code; reinforces that `capstone/` keeps domain logic behind interfaces so
  its AWS deployment (Ch 33/36) isn't welded to AWS. Notebook closes by pointing at the
  capstone's adapter boundaries.

## Dependencies
- Ch 32 (four primitives) · Ch 28 (hexagonal/ports-and-adapters) · Ch 33 (the AWS baseline to
  translate from).

## Phase-2 definition of done
- [ ] Runs top-to-bottom fully offline (no Azure/GCP/AWS account, no spend), deterministically.
- [ ] The parity table and the Azure-OpenAI / Vertex-AI / Bedrock framing match §34's content;
      the portability argument matches the §34.3 senior lens.
- [ ] The provider-swap demo proves business logic is unchanged across adapters.
- [ ] Recap + 2–3 reflection exercises ("translate service X to GCP", "where's the seam that
      makes a cloud swap feasible?"); no secrets, no network calls.
