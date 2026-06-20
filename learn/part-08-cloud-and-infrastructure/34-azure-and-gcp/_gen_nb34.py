import json
import uuid

cells = []


def _id():
    return uuid.uuid4().hex[:8]


def md(text):
    cells.append({
        "cell_type": "markdown",
        "id": _id(),
        "metadata": {},
        "source": text.splitlines(keepends=True),
    })


def code(text):
    cells.append({
        "cell_type": "code",
        "id": _id(),
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    })


# 1. Title + header
md(
    "# Translate the cloud, then prove portability\n"
    "\n"
    "> \U0001F4D3 *Companion to* **Modern Agentic AI Engineer** · Ch 34 §34.1–§34.3 · type: concept-lab\n"
    "\n"
    "**The promise:** by the end you can look at any AWS design and name the Azure and GCP "
    "equivalents on sight, and you can structure code so switching clouds is *feasible* — "
    "without paying the daily multi-cloud tax.\n"
    "\n"
    "Runs free and fully offline by design: there is **no Azure/GCP/AWS account and no spend**. "
    "The provider \"adapters\" here are in-memory fakes, so `MOCK=1` (default) is the only path — "
    "there is no live API to call."
)

# 2. Why this matters
md(
    "## \U0001F9E0 Why this matters\n"
    "\n"
    "A second cloud is *translation, not relearning*. Once you hold the four primitives from "
    "Chapter 32 — compute (containers), serverless functions, object storage, managed SQL — "
    "plus identity, every cloud is the same handful of boxes with different labels. Azure calls "
    "object storage *Blob Storage*; GCP calls it *Cloud Storage*; it's still \"a bucket you put "
    "bytes in.\" The console looks alien for an afternoon; the architecture is identical.\n"
    "\n"
    "The trap is concluding \"so let's run on *all* the clouds.\" Genuine multi-cloud multiplies "
    "your ops surface, dilutes your team's depth, and forfeits the managed services that make each "
    "cloud productive. The senior move (§34.3) is **portability *without* multi-cloud**: go deep "
    "on one cloud, but keep your domain logic behind interfaces so a swap is *possible* if a "
    "regulator or a resilience mandate ever forces it. This notebook makes both halves concrete — "
    "the translation map, and the hexagonal seam that keeps the swap cheap."
)

# 3. Objectives + prereqs
md(
    "## Objectives & prereqs\n"
    "\n"
    "**By the end you can:**\n"
    "- Translate an AWS service to its Azure and GCP equivalent by *primitive*, not by memorization.\n"
    "- Place the three managed model-access services — Bedrock, Azure OpenAI, Vertex AI — on the "
    "right cloud and explain when each pulls you in.\n"
    "- Build a single `ObjectStore` *port* with two interchangeable in-memory adapters, and prove "
    "the business logic doesn't change when you swap them.\n"
    "- Articulate the cost of real multi-cloud vs. the cheaper \"portable but single-cloud\" middle path.\n"
    "\n"
    "**Prereqs:** Chapter 32 (the four primitives) · Chapter 28 (hexagonal / ports-and-adapters — "
    "the seam) · Chapter 33 (AWS, the baseline we translate *from*). Read Chapter 34.\n"
    "\n"
    "**Packages:** standard library only. No SDKs, no network, no keys — in any mode."
)

# 4. Setup
code(
    "# Setup — imports, env, the MOCK switch, and a fixed seed.\n"
    "import json\n"
    "import os\n"
    "import random\n"
    "from pathlib import Path\n"
    "\n"
    "from dotenv import load_dotenv\n"
    "\n"
    "load_dotenv()  # reads a local .env if present; never hardcode keys\n"
    "\n"
    "# This chapter is offline BY DESIGN: the cloud adapters below are in-memory fakes,\n"
    "# so there is no live path and no spend. MOCK stays 1; we keep the switch only so\n"
    "# every notebook in the course reads the same way.\n"
    "MOCK = os.getenv(\"COMPANION_MOCK\", \"1\") == \"1\"\n"
    "\n"
    "random.seed(34)  # determinism for anything stochastic\n"
    "\n"
    "DATA = Path(\"data\")  # tiny committed fixtures live here\n"
    "\n"
    "print(f\"MOCK mode: {MOCK}  (offline, no Azure/GCP/AWS account, no spend)\")\n"
    "print(\"This notebook makes NO network calls in any mode.\")"
)

# 5a. Mental model: parity table
md(
    "## \U0001F9E0 The map: same primitives, different names\n"
    "\n"
    "Load the tiny committed parity table (`data/cloud-parity.json`) and print it. This is the "
    "entire mental model on one screen — five primitives plus the AI model-access row, across all "
    "three clouds. It mirrors the table in §34.1–§34.2."
)

code(
    "parity = json.loads((DATA / \"cloud-parity.json\").read_text(encoding=\"utf-8\"))\n"
    "\n"
    "rows = parity[\"primitives\"] + parity[\"model_access\"]\n"
    "\n"
    "# A small fixed-width print so the three clouds line up as columns.\n"
    "w_concept = max(len(r[\"concept\"]) for r in rows)\n"
    "w_aws = max(len(r[\"aws\"]) for r in rows)\n"
    "w_azure = max(len(r[\"azure\"]) for r in rows)\n"
    "\n"
    "header = f'{\"Concept\":<{w_concept}}  | {\"AWS\":<{w_aws}} | {\"Azure\":<{w_azure}} | GCP'\n"
    "print(header)\n"
    "print(\"-\" * len(header))\n"
    "for r in rows:\n"
    "    print(f'{r[\"concept\"]:<{w_concept}}  | {r[\"aws\"]:<{w_aws}} | {r[\"azure\"]:<{w_azure}} | {r[\"gcp\"]}')"
)

md(
    "**What you just saw.** Five rows cover most of what you deploy, and the *concept* column never "
    "changes — only the labels do. \"Where do I run a container? / store a blob? / who am I "
    "(identity)?\" has the same answer everywhere; you're learning a phrasebook, not a new language."
)

# 5b. Predict + translate drill
md(
    "## \U0001F52E Predict, then translate\n"
    "\n"
    "Below is a slice of the capstone's AWS deployment, described in primitives. **Before running "
    "the next cell, predict the Azure and GCP names for each line** — say them out loud:\n"
    "\n"
    "- the API runs as a container on **Fargate**\n"
    "- artifacts land in an **S3** bucket\n"
    "- a nightly cleanup is a **Lambda**\n"
    "- the app authenticates with **IAM** roles\n"
    "- the model calls go through **Bedrock**\n"
    "\n"
    "Now run `translate(...)` and check yourself against the committed table."
)

code(
    "# Build fast lookup indexes from the parity table: (cloud, lowercased service) -> row.\n"
    "_AWS_INDEX = {r[\"aws\"].lower(): r for r in rows}\n"
    "# Allow translating from a bare service name even when the cell wrote \"ECS / Fargate\".\n"
    "for r in rows:\n"
    "    for piece in r[\"aws\"].replace(\"/\", \" \").split():\n"
    "        _AWS_INDEX.setdefault(piece.lower(), r)\n"
    "\n"
    "\n"
    "def translate(aws_service: str, target_cloud: str) -> str:\n"
    "    \"\"\"Translate an AWS service name to its Azure or GCP equivalent.\n"
    "\n"
    "    Matching is forgiving: 'Fargate', 'fargate', or 'ECS / Fargate' all resolve\n"
    "    to the Containers row. Raises if the service or target cloud is unknown, so a\n"
    "    typo fails loudly instead of silently returning the wrong primitive.\n"
    "    \"\"\"\n"
    "    target = target_cloud.lower()\n"
    "    if target not in (\"azure\", \"gcp\"):\n"
    "        raise ValueError(f\"target_cloud must be 'azure' or 'gcp', got {target_cloud!r}\")\n"
    "    row = _AWS_INDEX.get(aws_service.strip().lower())\n"
    "    if row is None:\n"
    "        raise KeyError(f\"no parity row for AWS service {aws_service!r}\")\n"
    "    return row[target]\n"
    "\n"
    "\n"
    "aws_architecture = [\"Fargate\", \"S3\", \"Lambda\", \"IAM\", \"Bedrock\"]\n"
    "\n"
    "for svc in aws_architecture:\n"
    "    print(f'{svc:<8} -> Azure: {translate(svc, \"azure\"):<28} GCP: {translate(svc, \"gcp\")}')"
)

md(
    "**What you just saw.** Every AWS line had a one-hop equivalent on both clouds. The architecture "
    "diagram — its boxes and arrows — is unchanged; you re-labeled the boxes. That is what \"a "
    "second cloud is translation\" means in practice. If your prediction matched, you've already "
    "internalized the map."
)

# 5c. Model access angle
md(
    "## The model-access angle (not interchangeable labels)\n"
    "\n"
    "Most rows are pure synonyms. The **model-access** row is the one place the *choice* carries "
    "weight, because each cloud leads with a different model family and a different gravity:\n"
    "\n"
    "- **AWS Bedrock** — one API to several model families (the book's stack leans on **Claude** "
    "here); request and response stay inside your AWS perimeter. Default for us (Chapter 33).\n"
    "- **Azure OpenAI Service** — the **GPT** family inside Azure's enterprise security, compliance, "
    "and regional boundaries. This is *why* regulated enterprises standardize on Azure: the model "
    "access their compliance team will actually approve (§34.1).\n"
    "- **GCP Vertex AI** — Google's **Gemini** models on a unified ML platform, strongest where heavy "
    "data engineering meets ML (BigQuery, Dataflow sit right alongside). Compelling if your org "
    "already lives in BigQuery (§34.2).\n"
    "\n"
    "This is a comparison cell — **no live calls**. The point is *placement and pull*, not latency."
)

code(
    "# A pure-data comparison: which cloud, which model family, what pulls you there.\n"
    "model_access = {\n"
    "    \"AWS Bedrock\":          (\"Claude / Llama / Titan\", \"stays in your AWS perimeter; multi-family\"),\n"
    "    \"Azure OpenAI Service\": (\"GPT family\",             \"enterprise compliance + regional boundary\"),\n"
    "    \"GCP Vertex AI\":        (\"Gemini\",                 \"data/ML gravity (BigQuery, Dataflow)\"),\n"
    "}\n"
    "\n"
    "w = max(len(k) for k in model_access)\n"
    "for service, (family, pull) in model_access.items():\n"
    "    print(f\"{service:<{w}}  | {family:<24} | {pull}\")"
)

md(
    "**What you just saw.** Unlike \"S3 vs Blob,\" the model row isn't a free swap — picking the "
    "cloud here often *means* picking the model family and the compliance story. A senior chooses "
    "this row first (where's our model access approved?) and lets the rest of the primitives follow."
)

# 5d. Build: the portability seam
md(
    "## \U0001F527 The portability seam: one port, two adapters\n"
    "\n"
    "Here's the payoff. We define **one** `ObjectStore` *port* (the interface your app depends on), "
    "then two in-memory adapters that imitate the *shapes* of two different clouds — an \"S3-like\" "
    "store and a \"Blob-like\" store. They have different internal vocabulary on purpose (S3 talks "
    "*keys*; Blob talks *blobs in a container*), but they satisfy the same port.\n"
    "\n"
    "This is the hexagonal discipline from Chapter 28: business logic depends on the *port*, never on "
    "a concrete cloud SDK."
)

code(
    "from abc import ABC, abstractmethod\n"
    "\n"
    "\n"
    "class ObjectStore(ABC):\n"
    "    \"\"\"The PORT: the only object-storage vocabulary the app is allowed to know.\n"
    "\n"
    "    put(name, data) -> None ; get(name) -> bytes ; list_names() -> sorted list.\n"
    "    Domain code depends on THIS, never on boto3 / azure-storage-blob / gcs.\n"
    "    \"\"\"\n"
    "\n"
    "    @abstractmethod\n"
    "    def put(self, name: str, data: bytes) -> None: ...\n"
    "\n"
    "    @abstractmethod\n"
    "    def get(self, name: str) -> bytes: ...\n"
    "\n"
    "    @abstractmethod\n"
    "    def list_names(self) -> list[str]: ...\n"
    "\n"
    "\n"
    "class S3LikeStore(ObjectStore):\n"
    "    \"\"\"Adapter shaped like S3: a flat bucket of 'keys'. In-memory fake, no boto3.\"\"\"\n"
    "\n"
    "    def __init__(self, bucket: str):\n"
    "        self.bucket = bucket\n"
    "        self._keys: dict[str, bytes] = {}\n"
    "\n"
    "    def put(self, name: str, data: bytes) -> None:\n"
    "        self._keys[name] = data  # S3 vocabulary: object 'keys' in a bucket\n"
    "\n"
    "    def get(self, name: str) -> bytes:\n"
    "        return self._keys[name]\n"
    "\n"
    "    def list_names(self) -> list[str]:\n"
    "        return sorted(self._keys)\n"
    "\n"
    "\n"
    "class BlobLikeStore(ObjectStore):\n"
    "    \"\"\"Adapter shaped like Azure Blob: 'blobs' inside a 'container'. In-memory fake.\"\"\"\n"
    "\n"
    "    def __init__(self, container: str):\n"
    "        self.container = container\n"
    "        self._blobs: dict[str, bytes] = {}\n"
    "\n"
    "    def put(self, name: str, data: bytes) -> None:\n"
    "        self._blobs[name] = data  # Blob vocabulary: 'blobs' in a 'container'\n"
    "\n"
    "    def get(self, name: str) -> bytes:\n"
    "        return self._blobs[name]\n"
    "\n"
    "    def list_names(self) -> list[str]:\n"
    "        return sorted(self._blobs)\n"
    "\n"
    "\n"
    "print(\"Port:    ObjectStore (put / get / list_names)\")\n"
    "print(\"Adapters: S3LikeStore('bucket'), BlobLikeStore('container')  -- both in-memory fakes\")"
)

# 5e. Predict: what changes when we swap?
md(
    "## \U0001F52E Predict: what changes when you swap the adapter?\n"
    "\n"
    "The function below is the *business logic* — archive an artifact, then read it back and verify. "
    "It takes an `ObjectStore` and does **not** know which cloud it's talking to.\n"
    "\n"
    "We're about to run the *exact same* `archive_and_verify` through `S3LikeStore` and then through "
    "`BlobLikeStore`. **Predict before running:** how many lines of the business logic have to change "
    "to switch clouds? What will the two results be?"
)

code(
    "def archive_and_verify(store: ObjectStore, name: str, payload: bytes) -> dict:\n"
    "    \"\"\"Pure business logic: depends only on the ObjectStore PORT.\n"
    "\n"
    "    Note what's absent: no bucket vs container, no boto3 vs azure SDK, no cloud\n"
    "    name anywhere. That absence is the whole point.\n"
    "    \"\"\"\n"
    "    store.put(name, payload)\n"
    "    read_back = store.get(name)\n"
    "    return {\n"
    "        \"stored\": name,\n"
    "        \"round_trip_ok\": read_back == payload,\n"
    "        \"inventory\": store.list_names(),\n"
    "    }\n"
    "\n"
    "\n"
    "payload = b'{\"artifact\": \"capstone-export\", \"rows\": 2}'\n"
    "\n"
    "# Same call, two different clouds-by-shape. Business logic is byte-for-byte identical.\n"
    "result_s3 = archive_and_verify(S3LikeStore(\"capstone-artifacts\"), \"exports/run-001.json\", payload)\n"
    "result_blob = archive_and_verify(BlobLikeStore(\"capstone-artifacts\"), \"exports/run-001.json\", payload)\n"
    "\n"
    "print(\"via S3LikeStore  :\", result_s3)\n"
    "print(\"via BlobLikeStore:\", result_blob)\n"
    "print()\n"
    "print(\"identical behavior across adapters:\", result_s3 == result_blob)\n"
    "assert result_s3 == result_blob, \"business logic must not care which cloud it ran on\"\n"
    "print(\"assert passed -> the swap changed ZERO lines of business logic.\")"
)

md(
    "**What you just saw.** The answer to the prediction is **nothing** — zero lines of "
    "`archive_and_verify` changed, and the two results are identical. Swapping clouds meant "
    "constructing a *different adapter at the edge*; the core never knew. That is \"portability "
    "without multi-cloud\" made literal: the seam lives at the boundary, and the domain stays "
    "cloud-agnostic."
)

# 5f. Pitfall
md(
    "## ⚠️ Pitfall: chasing *real* multi-cloud\n"
    "\n"
    "It's tempting to read the demo above as \"great, now let's *run* on both clouds at once.\" "
    "That's the expensive mistake. Portability (the seam) is nearly free; **operating** everywhere "
    "is not."
)

code(
    "# A back-of-envelope contrast: the seam is cheap; running everywhere is not.\n"
    "single_cloud_portable = {\n"
    "    \"ops surface\":      \"1 cloud to monitor, patch, secure\",\n"
    "    \"team depth\":       \"deep on one platform\",\n"
    "    \"managed services\": \"use them fully (their value is the point)\",\n"
    "    \"swap cost\":        \"feasible: rebuild adapters at the seam\",\n"
    "    \"when\":             \"almost always (the default)\",\n"
    "}\n"
    "\n"
    "true_multi_cloud = {\n"
    "    \"ops surface\":      \"2-3x: every cloud monitored, patched, secured\",\n"
    "    \"team depth\":       \"diluted across platforms\",\n"
    "    \"managed services\": \"forfeited (must use the lowest common denominator)\",\n"
    "    \"swap cost\":        \"n/a -- you already pay the running cost daily\",\n"
    "    \"when\":             \"only a real regulatory / resilience mandate\",\n"
    "}\n"
    "\n"
    "w = max(len(k) for k in single_cloud_portable)\n"
    "print(f'{\"\":<{w}}  | PORTABLE single-cloud           | TRUE multi-cloud')\n"
    "print(\"-\" * 88)\n"
    "for k in single_cloud_portable:\n"
    "    print(f\"{k:<{w}}  | {single_cloud_portable[k]:<30} | {true_multi_cloud[k]}\")"
)

md(
    "**The fix.** Keep the *seam* (cheap optionality) and stay on *one* cloud (cheap operations). "
    "You get most of the swap-ability for a fraction of the cost. The portable-single-cloud column "
    "is the default; you only step into the multi-cloud column when a regulator or a hard resilience "
    "requirement forces you — and you go in knowing the bill (§34.3)."
)

# 6. Senior lens
md(
    "## \U0001F3AF Senior lens\n"
    "\n"
    "A senior treats \"which cloud\" and \"how portable\" as two separate decisions, and resists "
    "collapsing them.\n"
    "\n"
    "- **Go deep on one cloud.** Pick it for the reason that actually binds you — usually *model "
    "access and compliance* (the model-access row), not a feature checklist. Then use that cloud's "
    "managed services to the hilt; their leverage is why you chose a cloud at all.\n"
    "- **Keep domain logic cloud-agnostic behind interfaces.** Every cloud-specific call (storage, "
    "queues, model gateway) lives behind a port like the one above. This is the same hexagonal "
    "discipline as the LLM client in Chapter 11 and the seams in Chapter 28 — and it's what makes "
    "the swap a *bounded* edge change, not a rewrite.\n"
    "- **Reserve true multi-cloud for genuine mandates.** Regulatory data-residency across regions, "
    "or a resilience requirement that one provider can't meet. Anything less, and you're paying a "
    "daily tax for optionality you'll likely never exercise.\n"
    "\n"
    "The judgment in one line: *be welded to a cloud's managed services, never to its SDKs.*"
)

# 7. Recap
md(
    "## Recap\n"
    "\n"
    "- A second cloud is **translation, not relearning**: the four primitives plus identity are the "
    "same boxes with different labels (`ECS/Fargate ↔ Container Apps ↔ Cloud Run`, "
    "`S3 ↔ Blob ↔ Cloud Storage`, `IAM ↔ Entra ID ↔ IAM`).\n"
    "- The **model-access** row is the one that carries weight: **Bedrock** (Claude, AWS perimeter) "
    "· **Azure OpenAI** (GPT, enterprise compliance) · **Vertex AI** (Gemini, data/ML gravity). "
    "Often you pick the cloud *because* of this row.\n"
    "- A single **port** (`ObjectStore`) with swappable **adapters** proves the payoff: swapping "
    "clouds changed **zero** lines of business logic.\n"
    "- **Portability ≠ multi-cloud.** The seam is cheap; *operating* everywhere is expensive. Go deep "
    "on one cloud, keep the seam, reserve real multi-cloud for genuine mandates."
)

# 8. Exercises
md(
    "## Exercises\n"
    "\n"
    "Each task *changes* something; predict the outcome before you run it.\n"
    "\n"
    "1. **Translate to GCP.** Without scrolling up, predict the GCP equivalents of `Azure Functions`, "
    "`Entra ID + RBAC`, and `Azure SQL / Postgres`. Then extend `translate()` (or add an "
    "`_AZURE_INDEX`) so it can translate *from* Azure too, and check yourself against "
    "`data/cloud-parity.json`.\n"
    "2. **Add a primitive.** Add a \"Message queue\" row (`SQS` ↔ `Service Bus` ↔ `Pub/Sub`) to the "
    "fixture and re-run the table cell. Predict whether any *code* has to change to pick up the new "
    "row. (Answer: it shouldn't — the table is data.)\n"
    "3. **Find the seam.** Write a third adapter, `GcsLikeStore`, that satisfies `ObjectStore`, and "
    "run `archive_and_verify` through it. Predict the result before running. Where, exactly, is the "
    "one place a real cloud swap touches code — and where does it *not*?\n"
    "4. **Spot the leak.** Suppose `archive_and_verify` called `store.bucket` directly. Explain why "
    "that single line would re-weld the business logic to the S3 shape and break the `BlobLikeStore` "
    "path — then confirm by trying it."
)

code("# Exercise scratch space — your code here.\n")
code("# Exercise scratch space — your code here.\n")

# 9. Next
md(
    "## Next\n"
    "\n"
    "- **Book:** §34.1 (Azure for AI) · §34.2 (GCP for AI) · §34.3 (multi-cloud & portability — the "
    "senior lens). Back-references: Chapter 32 (four primitives), Chapter 28 (hexagonal), "
    "Chapter 33 (AWS baseline).\n"
    "- **The seam in production:** the `ObjectStore` port here is a toy version of the same "
    "discipline the [`llm-gateway`](../../../blueprints/llm-gateway/) blueprint uses to keep model "
    "access behind one interface — swap Bedrock for Azure OpenAI without touching callers.\n"
    "- **Where this leads (capstone):** this chapter adds no new capstone code on purpose. It "
    "reinforces that the [`capstone/`](../../../capstone/) keeps its domain logic behind interfaces, "
    "so its AWS deployment (Chapters 33 & 36) isn't *welded* to AWS. Open the capstone's adapter "
    "boundaries and find the ports — that's the cloud swap, already factored out."
)

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = (
    "c:/Users/User1/Documents/my_git/ai-book-creation/books/modern-agentic-ai-engineer/"
    "modern-agentic-ai-repo/learn/part-08-cloud-and-infrastructure/34-azure-and-gcp/"
    "34-01-parity-and-portability.ipynb"
)
with open(out, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
    f.write("\n")
print("wrote", out)
print("cells:", len(cells))
