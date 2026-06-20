"""Generator for 33-02-s3-dynamodb-sqs-on-moto.ipynb. Run, then delete."""
import json
from pathlib import Path

HERE = Path(__file__).parent


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(text)}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": _lines(text)}


def _lines(text):
    text = text.rstrip("\n")
    parts = text.split("\n")
    return [p + "\n" for p in parts[:-1]] + [parts[-1]]


cells = []

cells.append(md(
    "# S3, DynamoDB, and SQS — the data + messaging plane, locally\n"
    "\n"
    "> \U0001F4D3 *Companion to* **Modern Agentic AI Engineer** *· Ch 33 §33.4–§33.5 · type: walkthrough*\n"
    "\n"
    "*One-line promise:* exercise the capstone's **storage and queue plane** end-to-end — put/get "
    "an object, read/write an item, enqueue/consume a task — against **simulated AWS**, with "
    "**no account and no spend**."
))

cells.append(md(
    "## \U0001F9E0 Why this matters\n"
    "\n"
    "The async backbone you built by hand in Ch 30–31 (a data layer + a queue feeding workers) has "
    "managed AWS equivalents: **S3** for objects, **DynamoDB** for key–value items, **SQS** for the "
    "API→worker handoff. The trap is that you only discover the sharp edges — two-ARN S3, "
    "DynamoDB's typed-attribute JSON, SQS *at-least-once* delivery — when they bite in production. "
    "This notebook lets you run the **real `boto3` call shapes** for all three for free, so the API "
    "is muscle memory before there's a bill or an incident attached to it."
))

cells.append(md(
    "## Objectives & prereqs\n"
    "\n"
    "**By the end you can:**\n"
    "- Round-trip an artifact through **S3** (upload → list → download → verify bytes).\n"
    "- Model and query a session item in **DynamoDB** by key.\n"
    "- Send → receive → delete a task through **SQS** — the exact API↔worker handoff from Ch 31.\n"
    "- Explain what `receive_message` returns on an empty queue, and why consumers must be "
    "**idempotent**.\n"
    "\n"
    "**Prereqs:** `33-01` (identity); Ch 30 (data layer), Ch 31 (queues/workers).\n"
    "\n"
    "**Cost:** `local-sim only`. `MOCK=1` (default) drives an **in-process fake** that mirrors the "
    "`boto3` shapes — **free, offline, deterministic, no AWS account, no packages beyond "
    "`requirements.txt`.** Set `COMPANION_MOCK=0` *and* `pip install moto boto3` to run the **same "
    "code** against [`moto`](https://github.com/getmoto/moto) (still local, still free). ⚠️ Pointing "
    "these calls at a **real** AWS account would incur charges — that's an explicit opt-in exercise, "
    "never the default."
))

cells.append(md("## Setup"))

cells.append(code(
    "import json\n"
    "import os\n"
    "import random\n"
    "from pathlib import Path\n"
    "\n"
    "from dotenv import load_dotenv\n"
    "\n"
    "load_dotenv()  # reads a git-ignored .env if present; never hardcode keys\n"
    "\n"
    "# MOCK=1 (default) uses an in-notebook fake of S3/DynamoDB/SQS that mirrors the boto3 call\n"
    "# shapes, so this runs FREE, OFFLINE, and DETERMINISTICALLY with no AWS account and only the\n"
    "# packages in requirements.txt. MOCK=0 runs the SAME code against `moto` (needs the optional\n"
    "# `pip install moto boto3`) -- still local, still free. Real AWS is never the default.\n"
    "MOCK = os.getenv(\"COMPANION_MOCK\", \"1\") == \"1\"\n"
    "\n"
    "# LocalStack note: the SAME boto3 code points at a running LocalStack by setting one env var,\n"
    "# AWS_ENDPOINT_URL=http://localhost:4566 -- we read it but don't require it.\n"
    "ENDPOINT_URL = os.getenv(\"AWS_ENDPOINT_URL\")  # e.g. LocalStack; None by default\n"
    "REGION = os.getenv(\"AWS_REGION\", \"us-east-1\")\n"
    "\n"
    "random.seed(33)\n"
    "\n"
    "DATA = Path(\"data\")\n"
    "BUCKET = \"capstone-artifacts\"\n"
    "TABLE = \"capstone-sessions\"\n"
    "QUEUE = \"capstone-tasks\"\n"
    "\n"
    "print(\"MOCK =\", MOCK, \"| region =\", REGION, \"| endpoint =\", ENDPOINT_URL or \"(simulated)\")"
))

cells.append(md(
    "### The in-process fake (MOCK path)\n"
    "\n"
    "When `MOCK=1` we use a tiny in-memory stand-in for the three clients. It implements **only** the "
    "handful of methods this notebook calls — but with the **same names, parameters, and response "
    "envelopes** as real `boto3` (`put_object`, `get_object`, `put_item`, `query`, `send_message`, "
    "`receive_message`, `delete_message`). The whole point: the code you write below is *byte-for-byte* "
    "the code you'd run against AWS. (`MOCK=0` swaps this out for `moto`/LocalStack and nothing else "
    "changes.)"
))

cells.append(code(
    "import base64\n"
    "import hashlib\n"
    "import uuid\n"
    "\n"
    "\n"
    "class FakeS3:\n"
    "    def __init__(self):\n"
    "        self._objs = {}  # (bucket, key) -> bytes\n"
    "        self._buckets = set()\n"
    "\n"
    "    def create_bucket(self, Bucket, **_):\n"
    "        self._buckets.add(Bucket)\n"
    "        return {\"Location\": f\"/{Bucket}\"}\n"
    "\n"
    "    def put_object(self, Bucket, Key, Body):\n"
    "        body = Body.encode() if isinstance(Body, str) else Body\n"
    "        self._objs[(Bucket, Key)] = body\n"
    "        etag = hashlib.md5(body).hexdigest()  # noqa: S324 (etag shape, not security)\n"
    "        return {\"ETag\": f'\"{etag}\"'}\n"
    "\n"
    "    def list_objects_v2(self, Bucket, **_):\n"
    "        keys = sorted(k for (b, k) in self._objs if b == Bucket)\n"
    "        contents = [{\"Key\": k, \"Size\": len(self._objs[(Bucket, k)])} for k in keys]\n"
    "        return {\"KeyCount\": len(contents), \"Contents\": contents}\n"
    "\n"
    "    def get_object(self, Bucket, Key):\n"
    "        body = self._objs[(Bucket, Key)]\n"
    "        return {\"Body\": _ByteStream(body), \"ContentLength\": len(body)}\n"
    "\n"
    "\n"
    "class _ByteStream:\n"
    "    \"\"\"Mimics boto3's StreamingBody: .read() returns bytes.\"\"\"\n"
    "    def __init__(self, data):\n"
    "        self._data = data\n"
    "\n"
    "    def read(self):\n"
    "        return self._data\n"
    "\n"
    "\n"
    "class FakeDynamo:\n"
    "    def __init__(self):\n"
    "        self._items = {}  # table -> { session_id -> item }\n"
    "\n"
    "    def create_table(self, TableName, **_):\n"
    "        self._items.setdefault(TableName, {})\n"
    "        return {\"TableDescription\": {\"TableName\": TableName}}\n"
    "\n"
    "    def put_item(self, TableName, Item):\n"
    "        pk = Item[\"session_id\"][\"S\"]\n"
    "        self._items.setdefault(TableName, {})[pk] = Item\n"
    "        return {}\n"
    "\n"
    "    def query(self, TableName, KeyConditionExpression, ExpressionAttributeValues, **_):\n"
    "        # We only support the one shape this notebook uses: session_id = :sid\n"
    "        wanted = ExpressionAttributeValues[\":sid\"][\"S\"]\n"
    "        items = [self._items.get(TableName, {}).get(wanted)]\n"
    "        items = [i for i in items if i is not None]\n"
    "        return {\"Items\": items, \"Count\": len(items)}\n"
    "\n"
    "\n"
    "class FakeSQS:\n"
    "    def __init__(self):\n"
    "        self._queues = {}  # url -> list[ {Body, ReceiptHandle, MessageId} ]\n"
    "\n"
    "    def create_queue(self, QueueName, **_):\n"
    "        url = f\"https://sqs.local/{QueueName}\"\n"
    "        self._queues.setdefault(url, [])\n"
    "        return {\"QueueUrl\": url}\n"
    "\n"
    "    def send_message(self, QueueUrl, MessageBody):\n"
    "        mid = uuid.UUID(int=random.getrandbits(128)).hex  # seeded -> deterministic\n"
    "        self._queues[QueueUrl].append(\n"
    "            {\"Body\": MessageBody, \"ReceiptHandle\": \"rh-\" + mid, \"MessageId\": mid}\n"
    "        )\n"
    "        return {\"MessageId\": mid}\n"
    "\n"
    "    def receive_message(self, QueueUrl, MaxNumberOfMessages=1, **_):\n"
    "        q = self._queues.get(QueueUrl, [])\n"
    "        msgs = q[:MaxNumberOfMessages]\n"
    "        # boto3 OMITS the 'Messages' key entirely when the queue is empty.\n"
    "        return {\"Messages\": msgs} if msgs else {}\n"
    "\n"
    "    def delete_message(self, QueueUrl, ReceiptHandle):\n"
    "        q = self._queues.get(QueueUrl, [])\n"
    "        self._queues[QueueUrl] = [m for m in q if m[\"ReceiptHandle\"] != ReceiptHandle]\n"
    "        return {}\n"
    "\n"
    "\n"
    "print(\"fakes defined (S3, DynamoDB, SQS) — same call shapes as boto3\")"
))

cells.append(md(
    "### One switch, three clients\n"
    "\n"
    "This is the only cell that knows about `MOCK`. Everything after it calls `s3`, `ddb`, `sqs` "
    "and is identical whether it's hitting the fake, `moto`, or (if you opted in) LocalStack. That "
    "is the payoff of coding to the `boto3` interface."
))

cells.append(code(
    "if MOCK:\n"
    "    s3, ddb, sqs = FakeS3(), FakeDynamo(), FakeSQS()\n"
    "else:\n"
    "    # MOCK=0: same code, real boto3 client, against moto or LocalStack (never real AWS\n"
    "    # unless YOU set AWS_ENDPOINT_URL to a real endpoint and accept the charges).\n"
    "    import boto3\n"
    "    from moto import mock_aws\n"
    "\n"
    "    if not ENDPOINT_URL:\n"
    "        # No LocalStack endpoint -> spin up moto in-process for this notebook.\n"
    "        _moto = mock_aws()\n"
    "        _moto.start()\n"
    "    kw = {\"region_name\": REGION}\n"
    "    if ENDPOINT_URL:\n"
    "        kw[\"endpoint_url\"] = ENDPOINT_URL  # LocalStack\n"
    "    s3 = boto3.client(\"s3\", **kw)\n"
    "    ddb = boto3.client(\"dynamodb\", **kw)\n"
    "    sqs = boto3.client(\"sqs\", **kw)\n"
    "\n"
    "# Provision the three resources (no-ops if they exist). Same calls on every backend.\n"
    "s3.create_bucket(Bucket=BUCKET)\n"
    "ddb.create_table(\n"
    "    TableName=TABLE,\n"
    "    KeySchema=[{\"AttributeName\": \"session_id\", \"KeyType\": \"HASH\"}],\n"
    "    AttributeDefinitions=[{\"AttributeName\": \"session_id\", \"AttributeType\": \"S\"}],\n"
    "    BillingMode=\"PAY_PER_REQUEST\",\n"
    ")\n"
    "queue_url = sqs.create_queue(QueueName=QUEUE)[\"QueueUrl\"]\n"
    "print(\"provisioned:\", BUCKET, \"|\", TABLE, \"|\", queue_url)"
))

cells.append(md(
    "## S3: round-trip an artifact\n"
    "\n"
    "S3 is the capstone's home for model artifacts and exports. We upload the tiny fixture in "
    "`data/sample-artifact.json`, list the bucket, download it back, and assert the bytes survived "
    "the trip. **Recall the two-ARN lesson from `33-01`:** the identity doing this needs "
    "`s3:PutObject`/`s3:GetObject` on `…/*` *and* `s3:ListBucket` on the bucket itself."
))

cells.append(code(
    "artifact_bytes = (DATA / \"sample-artifact.json\").read_bytes()\n"
    "key = \"exports/capstone-export-v3.json\"\n"
    "\n"
    "put = s3.put_object(Bucket=BUCKET, Key=key, Body=artifact_bytes)\n"
    "print(\"uploaded:\", key, \"| ETag:\", put[\"ETag\"])\n"
    "\n"
    "listing = s3.list_objects_v2(Bucket=BUCKET)\n"
    "print(\"objects in bucket:\", [(o[\"Key\"], o[\"Size\"]) for o in listing.get(\"Contents\", [])])\n"
    "\n"
    "downloaded = s3.get_object(Bucket=BUCKET, Key=key)[\"Body\"].read()\n"
    "assert downloaded == artifact_bytes, \"bytes did not round-trip!\"\n"
    "print(\"round-trip OK — bytes identical:\", len(downloaded), \"bytes\")"
))

cells.append(md(
    "## DynamoDB: a session item\n"
    "\n"
    "DynamoDB is the managed key–value store for known-access-pattern data like a **session store**. "
    "Its one bit of friction: items are *typed-attribute* JSON — every value is wrapped with its type "
    "(`{\"S\": ...}` string, `{\"N\": ...}` number). We `put_item` a session keyed by `session_id`, "
    "then `query` it back by that key."
))

cells.append(code(
    "session_item = {\n"
    "    \"session_id\": {\"S\": \"sess-001\"},        # partition key (string)\n"
    "    \"user\": {\"S\": \"ada@example.com\"},\n"
    "    \"turns\": {\"N\": \"3\"},                     # numbers are STRINGS in the wire format\n"
    "    \"last_intent\": {\"S\": \"summarize_export\"},\n"
    "}\n"
    "ddb.put_item(TableName=TABLE, Item=session_item)\n"
    "\n"
    "got = ddb.query(\n"
    "    TableName=TABLE,\n"
    "    KeyConditionExpression=\"session_id = :sid\",\n"
    "    ExpressionAttributeValues={\":sid\": {\"S\": \"sess-001\"}},\n"
    ")\n"
    "print(\"items returned:\", got[\"Count\"])\n"
    "print(\"the session:\", json.dumps(got[\"Items\"][0], indent=2))"
))

cells.append(md(
    "## SQS: the API→worker handoff\n"
    "\n"
    "SQS is the broker that carries a task from your API to a Celery-style worker (the Ch 31 "
    "pattern). The lifecycle is always **send → receive → process → delete**: a received message "
    "is only *hidden* (visibility timeout), not gone, until you explicitly `delete_message`. Forget "
    "the delete and the task gets redelivered — which is the heart of the pitfall below."
))

cells.append(code(
    "# API side: enqueue a task.\n"
    "task = {\"task\": \"summarize\", \"session_id\": \"sess-001\", \"s3_key\": key}\n"
    "send = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(task))\n"
    "print(\"enqueued MessageId:\", send[\"MessageId\"][:12], \"...\")\n"
    "\n"
    "# Worker side: receive, process, delete.\n"
    "resp = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)\n"
    "msg = resp[\"Messages\"][0]\n"
    "payload = json.loads(msg[\"Body\"])\n"
    "print(\"worker received:\", payload)\n"
    "\n"
    "# ... do the work here ...\n"
    "sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg[\"ReceiptHandle\"])\n"
    "print(\"processed & deleted — handoff complete\")"
))

cells.append(md(
    "### \U0001F52E Predict\n"
    "\n"
    "We just received and **deleted** the only message. Now we call `receive_message` again on the "
    "**empty** queue.\n"
    "\n"
    "**Predict:** what does the response look like? Specifically — is there a `\"Messages\"` key with an "
    "empty list `[]`, or is the key **absent** entirely? (This exact distinction has crashed many a "
    "worker.) Write your answer, then run."
))

cells.append(code(
    "empty = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)\n"
    "print(\"raw response on empty queue:\", empty)\n"
    "print(\"'Messages' key present?\", \"Messages\" in empty)\n"
    "\n"
    "# The safe consumer pattern: .get('Messages', []), never resp['Messages'].\n"
    "for m in empty.get(\"Messages\", []):\n"
    "    print(\"would process:\", m)\n"
    "print(\"empty-queue handled safely with .get('Messages', [])\")"
))

cells.append(md(
    "**What you just saw.** Real SQS (and our fake, faithfully) **omits the `Messages` key entirely** "
    "when nothing is available — it does *not* return `{\"Messages\": []}`. So `resp[\"Messages\"]` "
    "raises `KeyError` on every empty long-poll, which in a worker loop is a crash every few seconds. "
    "Always `resp.get(\"Messages\", [])`."
))

cells.append(md(
    "### ⚠️ Pitfall: SQS is *at-least-once* — make the consumer idempotent\n"
    "\n"
    "Standard SQS guarantees **at-least-once** delivery, not exactly-once. A visibility-timeout expiry, "
    "a worker crash between processing and `delete_message`, or a redrive will hand you the **same "
    "message twice**. If your handler isn't idempotent, that means a double charge, a duplicate email, "
    "or a second row. Below we redeliver a task and show a naïve counter double-counting, then an "
    "idempotent handler keyed on a dedupe id (the Ch 29/31 discipline)."
))

cells.append(code(
    "# Simulate at-least-once: the SAME task arrives twice (e.g. timeout fired before delete).\n"
    "dupe = {\"task_id\": \"job-77\", \"action\": \"charge\", \"amount\": 49}\n"
    "deliveries = [dupe, dupe]  # delivered twice\n"
    "\n"
    "# Naive handler: no dedupe -> charges twice.\n"
    "charged_naive = 0\n"
    "for d in deliveries:\n"
    "    charged_naive += d[\"amount\"]\n"
    "print(\"naive total charged:\", charged_naive, \"(should be 49!) <- the bug\")\n"
    "\n"
    "# Idempotent handler: skip already-seen task_ids.\n"
    "processed = set()\n"
    "charged_safe = 0\n"
    "for d in deliveries:\n"
    "    if d[\"task_id\"] in processed:\n"
    "        print(\"  duplicate\", d[\"task_id\"], \"-> skipped\")\n"
    "        continue\n"
    "    processed.add(d[\"task_id\"])\n"
    "    charged_safe += d[\"amount\"]\n"
    "print(\"idempotent total charged:\", charged_safe, \"(correct)\")"
))

cells.append(md(
    "## \U0001F3AF Senior lens: a simulator mirrors *shape*, not every *guarantee*\n"
    "\n"
    "Both our fake and `moto` reproduce the API **shape** — method names, parameters, response "
    "envelopes — and that's enough to learn the calls and catch shape bugs for free. What they "
    "**don't** reproduce is the distributed reality: DynamoDB's eventual consistency on global "
    "secondary indexes, SQS's actual at-least-once redelivery timing and visibility windows, S3's "
    "read-after-write nuances, IAM enforcement, throttling, and per-service quotas. So treat green "
    "here as “my code shapes are right,” not “this is production-correct.” Before you trust it live, "
    "run an integration test against **LocalStack** (one env var: `AWS_ENDPOINT_URL`) or a "
    "throwaway real-AWS sandbox — that's where consistency and at-least-once actually show up. Mock "
    "for fast feedback; integration-test for truth."
))

cells.append(md(
    "## Recap\n"
    "\n"
    "- **S3 / DynamoDB / SQS** are the managed forms of the Ch 30–31 data + queue plane; you just "
    "drove all three with real `boto3` shapes for free.\n"
    "- **DynamoDB items are typed-attribute JSON** (`{\"S\": ...}`, `{\"N\": ...}`) — numbers ride the "
    "wire as strings.\n"
    "- **SQS omits `Messages` on an empty queue** — always `resp.get(\"Messages\", [])`.\n"
    "- **SQS is at-least-once** — design consumers to be **idempotent** (dedupe on a stable id).\n"
    "- A simulator mirrors **shape, not guarantees** — integration-test against LocalStack/real AWS "
    "before trusting consistency and delivery.\n"
    "- **One `endpoint_url` / `AWS_ENDPOINT_URL`** repoints the identical code at LocalStack — no "
    "code change."
))

cells.append(md(
    "## Exercises\n"
    "\n"
    "1. **Object-not-found.** `get_object` a key you never uploaded. \U0001F52E Predict the failure "
    "shape (real S3 raises a `NoSuchKey` client error), then handle it gracefully in the consumer.\n"
    "2. **Update, don't clobber.** Bump the session's `turns` from 3 to 4. Sketch the real-AWS "
    "`update_item` with an `UpdateExpression` (`SET turns = :n`) rather than re-`put_item`ing the "
    "whole object — why is that safer under concurrency?\n"
    "3. **Batch receive.** Send 5 messages, then `receive_message(MaxNumberOfMessages=10)`. How many "
    "come back, and why might real SQS return *fewer* than you sent in one call (it samples a subset "
    "of servers)?\n"
    "4. **Point at LocalStack.** Start LocalStack, export `AWS_ENDPOINT_URL=http://localhost:4566`, "
    "set `COMPANION_MOCK=0`, and re-run. Confirm the data plane behaves identically — then note one "
    "behavior the fake got *wrong* that LocalStack got right."
))

cells.append(code("# Exercise 1 — get_object on a missing key; handle the not-found gracefully.\n"))
cells.append(code("# Exercise 2 — update_item with an UpdateExpression (sketch the real-AWS call).\n"))
cells.append(code("# Exercise 3 — send 5, receive up to 10; observe the count.\n"))

cells.append(md(
    "## Next\n"
    "\n"
    "- **Next notebook:** [`33-03-bedrock-call-and-capstone-deploy-notes.ipynb`](./33-03-bedrock-call-and-capstone-deploy-notes.ipynb) "
    "— a mocked Amazon Bedrock model call, then the full component→service deploy map for the "
    "capstone (the chapter's \U0001F527 Build).\n"
    "- **Previous:** [`33-01-iam-and-least-privilege.ipynb`](./33-01-iam-and-least-privilege.ipynb) "
    "— the least-privilege identities these services run under.\n"
    "- **Feeds the capstone:** this S3 + DynamoDB + SQS plane is what "
    "[`capstone/infra/`](../../../capstone/) stands up for real; the Ch 36 Terraform "
    "([`templates/terraform-module/`](../../../templates/terraform-module/)) provisions it. The "
    "queue-worker shape ties to the async backbone in book §31. See book §33.4–§33.5."
))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = HERE / "33-02-s3-dynamodb-sqs-on-moto.ipynb"
out.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
print("wrote", out, "cells:", len(cells))
