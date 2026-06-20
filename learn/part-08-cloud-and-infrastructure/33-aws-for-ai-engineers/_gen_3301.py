"""Generator for 33-01-iam-and-least-privilege.ipynb. Run, then delete."""
import json
from pathlib import Path

HERE = Path(__file__).parent


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(text)}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": _lines(text)}


def _lines(text):
    # Preserve newlines per-line as nbformat expects (each element ends with \n
    # except the last). Keep a trailing newline off the final line.
    text = text.rstrip("\n")
    parts = text.split("\n")
    return [p + "\n" for p in parts[:-1]] + [parts[-1]]


cells = []

cells.append(md(
    "# IAM and least privilege, simulated\n"
    "\n"
    "> \U0001F4D3 *Companion to* **Modern Agentic AI Engineer** *· Ch 33 §33.1 · type: walkthrough*\n"
    "\n"
    "*One-line promise:* write a **least-privilege** IAM policy and prove it allows exactly "
    "what's needed and denies the rest — with **no AWS account, no spend**."
))

cells.append(md(
    "## \U0001F9E0 Why this matters\n"
    "\n"
    "IAM is the foundation every other AWS service rests on, and the most common source of both "
    "breaches and 3 a.m. frustration. A policy is just a JSON document answering one question: "
    "*who can do what to which resource.* Get it too tight and your service can't read its own "
    "bucket; get it too loose and one compromised container becomes a full-account breach. The "
    "discipline that bounds that blast radius is **least privilege** — grant the minimum, "
    "nothing more — and the senior habit that makes it safe to operate is **roles, not "
    "long-lived keys.** You can practice both right here, offline, before a single real credential "
    "is at stake."
))

cells.append(md(
    "## Objectives & prereqs\n"
    "\n"
    "**By the end you can:**\n"
    "- Read an IAM policy as the `Effect` / `Action` / `Resource` triple it really is.\n"
    "- Author a tight policy that reads *one* S3 bucket and nothing else.\n"
    "- Evaluate allowed-vs-denied actions with a tiny policy simulator — the same logic "
    "AWS's IAM evaluation uses (explicit deny wins; default is deny).\n"
    "- Explain why services should **assume a role** at runtime instead of carrying access keys.\n"
    "\n"
    "**Prereqs:** Ch 32 (the four primitives — here it's *identity*). The `boto3` shape from "
    "Ch 11/30 helps but isn't required.\n"
    "\n"
    "**Cost:** `local-sim only`. `MOCK=1` (default) runs a pure-stdlib policy simulator — "
    "**free, offline, deterministic, no AWS account.** There is no live-API path for this notebook: "
    "IAM evaluation stays simulated by design. (An optional cell shows the *same* check against "
    "[`moto`](https://github.com/getmoto/moto) if you've `pip install moto boto3` — still no "
    "real AWS.)"
))

cells.append(md("## Setup"))

cells.append(code(
    "import json\n"
    "import os\n"
    "import random\n"
    "from fnmatch import fnmatch\n"
    "\n"
    "from dotenv import load_dotenv\n"
    "\n"
    "load_dotenv()  # reads a git-ignored .env if present; never hardcode keys\n"
    "\n"
    "# MOCK=1 (the default) runs everything against an in-notebook policy simulator so this\n"
    "# notebook is FREE, OFFLINE, and DETERMINISTIC with no AWS account. There is deliberately\n"
    "# NO live-AWS path here — IAM policy evaluation is something you want to rehearse in a\n"
    "# sandbox, not against a real account.\n"
    "MOCK = os.getenv(\"COMPANION_MOCK\", \"1\") == \"1\"\n"
    "\n"
    "# Optional extras (NOT in requirements.txt): `pip install moto boto3` unlocks the one\n"
    "# bonus cell that runs the SAME check through moto's IAM. The notebook is complete without it.\n"
    "random.seed(33)  # reproducibility for anything we shuffle\n"
    "\n"
    "BUCKET = \"capstone-artifacts\"\n"
    "print(\"MOCK =\", MOCK, \"| sandbox bucket =\", BUCKET)"
))

cells.append(md(
    "## \U0001F9E0 Mental model: a policy is `(Effect, Action, Resource)` rows\n"
    "\n"
    "Strip away the JSON ceremony and an IAM policy is a little table of rules. Each statement says: "
    "for this **Action** (`s3:GetObject`) on this **Resource** (`arn:aws:s3:::bucket/*`), the "
    "**Effect** is `Allow` or `Deny`. Evaluation has two rules you must internalize:\n"
    "\n"
    "1. **Default deny.** If nothing explicitly allows the action, it's denied.\n"
    "2. **Explicit deny wins.** A `Deny` anywhere overrides any `Allow`.\n"
    "\n"
    "Policies attach to **users**, **roles**, and **groups** — the *identities* from Ch 32. "
    "Below we author one policy and run those two rules by hand, so the evaluation is never magic."
))

cells.append(md(
    "### The policy we want: read one bucket, nothing more\n"
    "\n"
    "The capstone's worker needs to read artifacts from a single S3 bucket. That's the whole "
    "requirement — so that's the whole policy. List the bucket, get objects under it, and "
    "stop. Notice the two-ARN shape: `s3:ListBucket` acts on the **bucket** ARN, while "
    "`s3:GetObject` acts on the **objects** ARN (`/*`). Mixing those up is the #1 reason a "
    "“correct-looking” S3 policy mysteriously fails."
))

cells.append(code(
    "least_privilege_policy = {\n"
    "    \"Version\": \"2012-10-17\",\n"
    "    \"Statement\": [\n"
    "        {\n"
    "            \"Sid\": \"ListTheOneBucket\",\n"
    "            \"Effect\": \"Allow\",\n"
    "            \"Action\": [\"s3:ListBucket\"],\n"
    "            \"Resource\": [f\"arn:aws:s3:::{BUCKET}\"],\n"
    "        },\n"
    "        {\n"
    "            \"Sid\": \"ReadObjectsInThatBucket\",\n"
    "            \"Effect\": \"Allow\",\n"
    "            \"Action\": [\"s3:GetObject\"],\n"
    "            \"Resource\": [f\"arn:aws:s3:::{BUCKET}/*\"],\n"
    "        },\n"
    "    ],\n"
    "}\n"
    "print(json.dumps(least_privilege_policy, indent=2))"
))

cells.append(md(
    "### A tiny policy simulator\n"
    "\n"
    "This mirrors how AWS's *policy simulator* answers “would this request be allowed?” for a "
    "given `(action, resource)`. We gather matching statements, then apply the two rules: an "
    "explicit `Deny` wins; otherwise an `Allow` permits; otherwise the default is deny. Wildcards "
    "(`s3:*`, `*`) match with `fnmatch`, exactly like IAM's `*` semantics."
))

cells.append(code(
    "def evaluate(policy, action, resource):\n"
    "    \"\"\"Return 'Allow' or 'Deny' for (action, resource) under `policy`.\n"
    "    Rules, in order of precedence: explicit Deny > Allow > default Deny.\"\"\"\n"
    "    decision = \"Deny (default)\"\n"
    "    for stmt in policy[\"Statement\"]:\n"
    "        actions = stmt[\"Action\"]\n"
    "        actions = [actions] if isinstance(actions, str) else actions\n"
    "        resources = stmt[\"Resource\"]\n"
    "        resources = [resources] if isinstance(resources, str) else resources\n"
    "        action_hit = any(fnmatch(action, a) for a in actions)\n"
    "        resource_hit = any(fnmatch(resource, r) for r in resources)\n"
    "        if action_hit and resource_hit:\n"
    "            if stmt[\"Effect\"] == \"Deny\":\n"
    "                return \"Deny (explicit)\"  # explicit deny wins immediately\n"
    "            decision = \"Allow\"\n"
    "    return decision\n"
    "\n"
    "\n"
    "# Sanity: the thing the worker actually needs is allowed.\n"
    "print(evaluate(least_privilege_policy, \"s3:GetObject\", f\"arn:aws:s3:::{BUCKET}/sess-001.json\"))"
))

cells.append(md(
    "### \U0001F52E Predict\n"
    "\n"
    "Our policy allows `s3:GetObject` on `arn:aws:s3:::capstone-artifacts/*`. A teammate's code "
    "tries to read from a **different** bucket:\n"
    "\n"
    "```\n"
    "action   = s3:GetObject\n"
    "resource = arn:aws:s3:::someone-elses-bucket/secret.txt\n"
    "```\n"
    "\n"
    "**Predict:** does the simulator return `Allow` or `Deny`? And what about `s3:DeleteObject` on "
    "*our own* bucket? Write down both answers, then run the next cell."
))

cells.append(code(
    "checks = [\n"
    "    (\"s3:GetObject\",    f\"arn:aws:s3:::{BUCKET}/sess-001.json\"),        # needed → expect Allow\n"
    "    (\"s3:ListBucket\",   f\"arn:aws:s3:::{BUCKET}\"),                       # needed → expect Allow\n"
    "    (\"s3:GetObject\",    \"arn:aws:s3:::someone-elses-bucket/secret.txt\"),# other bucket → Deny\n"
    "    (\"s3:DeleteObject\", f\"arn:aws:s3:::{BUCKET}/sess-001.json\"),         # not granted → Deny\n"
    "    (\"iam:CreateUser\",  \"*\"),                                            # nowhere near → Deny\n"
    "]\n"
    "for action, resource in checks:\n"
    "    print(f\"{evaluate(least_privilege_policy, action, resource):16} {action:18} {resource}\")"
))

cells.append(md(
    "**What you just saw.** Exactly two actions are allowed — the two the worker needs — and "
    "everything else, including a read of someone else's bucket and a *delete* of our own objects, "
    "is denied by **default**, with no `Deny` statement required. That asymmetry is the whole point "
    "of least privilege: you enumerate the small set you grant; the enormous set you didn't name is "
    "refused for free."
))

cells.append(md(
    "### ⚠️ Pitfall: the `\"Action\": \"s3:*\", \"Resource\": \"*\"` trap\n"
    "\n"
    "The fastest way to make an error message go away is to broaden the policy until it stops "
    "complaining — and the broadest possible grant is `s3:*` on `*` (or worse, `*:*`). It "
    "“works,” which is exactly why it's dangerous: now any code running under this identity "
    "can read, overwrite, or **delete every object in every bucket** in the account. Watch the blast "
    "radius widen, then scope it back."
))

cells.append(code(
    "wide_open = {\n"
    "    \"Version\": \"2012-10-17\",\n"
    "    \"Statement\": [{\"Effect\": \"Allow\", \"Action\": \"s3:*\", \"Resource\": \"*\"}],\n"
    "}\n"
    "\n"
    "danger = [\n"
    "    (\"s3:DeleteObject\", \"arn:aws:s3:::prod-customer-pii/ssn.csv\"),\n"
    "    (\"s3:GetObject\",    \"arn:aws:s3:::another-teams-secrets/key.pem\"),\n"
    "    (\"s3:PutObject\",    \"arn:aws:s3:::billing-exports/2026.csv\"),\n"
    "]\n"
    "print(\"Under  s3:* on *  — the blast radius:\")\n"
    "for action, resource in danger:\n"
    "    print(f\"  {evaluate(wide_open, action, resource):16} {action:16} {resource}\")\n"
    "\n"
    "print(\"\\nUnder our least-privilege policy — same requests:\")\n"
    "for action, resource in danger:\n"
    "    print(f\"  {evaluate(least_privilege_policy, action, resource):16} {action:16} {resource}\")"
))

cells.append(md(
    "The wide-open policy waves through a delete of customer PII and a read of another team's private "
    "key. The scoped policy denies all three by default. Same one-line difference (`s3:*` on `*` vs. "
    "two named actions on one bucket) — wildly different worst case. **Scope every policy to the "
    "actions and resources you can name.**"
))

cells.append(md(
    "### Optional bonus: the same check through `moto` (no real AWS)\n"
    "\n"
    "If you've installed the extras (`pip install moto boto3`), `moto` gives you an in-process IAM "
    "that speaks the real `boto3` API — you can `create_policy` and call the real "
    "`simulate_custom_policy` shape. This is here only to show the call shapes match real AWS; the "
    "notebook is complete without it, so it fails *soft* if the packages or the simulate API aren't "
    "available."
))

cells.append(code(
    "try:\n"
    "    import boto3\n"
    "    from moto import mock_aws\n"
    "\n"
    "    @mock_aws\n"
    "    def run():\n"
    "        iam = boto3.client(\"iam\", region_name=\"us-east-1\")\n"
    "        arn = iam.create_policy(\n"
    "            PolicyName=\"read-one-bucket\",\n"
    "            PolicyDocument=json.dumps(least_privilege_policy),\n"
    "        )[\"Policy\"][\"Arn\"]\n"
    "        # Same boto3 call shape you'd use against real AWS:\n"
    "        result = iam.simulate_custom_policy(\n"
    "            PolicyInputList=[json.dumps(least_privilege_policy)],\n"
    "            ActionNames=[\"s3:GetObject\", \"s3:DeleteObject\"],\n"
    "            ResourceArns=[f\"arn:aws:s3:::{BUCKET}/sess-001.json\"],\n"
    "        )\n"
    "        for r in result[\"EvaluationResults\"]:\n"
    "            print(f\"  {r['EvalActionName']:16} -> {r['EvalDecision']}\")\n"
    "        return arn\n"
    "\n"
    "    print(\"moto IAM evaluation (real boto3 shapes):\")\n"
    "    run()\n"
    "except ImportError:\n"
    "    print(\"Optional: `pip install moto boto3` to run this bonus cell. Skipped — the\")\n"
    "    print(\"stdlib simulator above already taught the evaluation rules.\")\n"
    "except Exception as e:  # moto's simulate support varies by version; fail soft\n"
    "    print(\"moto present but simulate_custom_policy unavailable in this version:\", type(e).__name__)\n"
    "    print(\"No problem — the stdlib simulator is the source of truth for this lesson.\")"
))

cells.append(md(
    "## \U0001F3AF Senior lens: roles, not long-lived keys\n"
    "\n"
    "Notice we never created an access key. In production you go further: services don't *hold* "
    "credentials at all. Your Fargate task or Lambda is given an **IAM role** it **assumes** at "
    "runtime, and AWS hands it short-lived, auto-rotating credentials scoped to that role's policies. "
    "Nothing long-lived lives in your code, your env, or your image to leak. The two habits compound: "
    "*least privilege* bounds what any one identity can do, and *roles-not-keys* means there's no "
    "static secret to steal in the first place. When you read the capstone deploy map in `33-03`, "
    "every component there assumes its own tightly-scoped role — this is why."
))

cells.append(md(
    "## Recap\n"
    "\n"
    "- An IAM policy is a table of `(Effect, Action, Resource)` rules; **default is deny** and "
    "**explicit deny wins**.\n"
    "- Least privilege = grant the small set you can *name*; everything else is refused for free.\n"
    "- `s3:ListBucket` targets the **bucket** ARN; `s3:GetObject` targets the **objects** (`/*`) ARN "
    "— don't conflate them.\n"
    "- `s3:*` on `*` “works” and is a breach waiting to happen; scope to named actions and "
    "resources.\n"
    "- Prefer **roles assumed at runtime** over long-lived keys — no static secret to leak."
))

cells.append(md(
    "## Exercises\n"
    "\n"
    "1. **Add a write path, carefully.** The worker now needs to write *results* back under "
    "`{BUCKET}/results/*` (and only there). Add one statement granting `s3:PutObject` scoped to that "
    "prefix. \U0001F52E Predict whether `PutObject` to `{BUCKET}/raw/x.json` is then allowed, and "
    "confirm with `evaluate`.\n"
    "2. **Make explicit-deny win.** Add a `Deny` statement for `s3:DeleteObject` on `{BUCKET}/*` "
    "*on top of* a policy that also `Allow`s `s3:*` on the bucket. Show the delete is denied even "
    "though an `Allow` matches — proving precedence.\n"
    "3. **A condition key.** Sketch (in a comment) how you'd restrict the read to requests from "
    "inside the VPC using a `Condition` block (`aws:SourceVpc`). Why is that defense-in-depth on top "
    "of least privilege?\n"
    "4. **Group vs. role.** In two sentences, when do you attach a policy to a *group* (humans) "
    "versus have a service *assume a role*? Tie it to the roles-not-keys habit."
))

cells.append(code("# Exercise 1 — add a scoped s3:PutObject under results/*, then evaluate.\n"))
cells.append(code("# Exercise 2 — explicit Deny over a broad Allow; show precedence.\n"))
cells.append(code("# Exercise 3 — a Condition block restricting to the VPC (sketch in comments).\n"))

cells.append(md(
    "## Next\n"
    "\n"
    "- **Next notebook:** [`33-02-s3-dynamodb-sqs-on-moto.ipynb`](./33-02-s3-dynamodb-sqs-on-moto.ipynb) "
    "— drive the capstone's storage + messaging plane (S3, DynamoDB, SQS) against simulated AWS, "
    "using these same identities.\n"
    "- **Then:** [`33-03-bedrock-call-and-capstone-deploy-notes.ipynb`](./33-03-bedrock-call-and-capstone-deploy-notes.ipynb) "
    "— a mocked Bedrock call and the full component→service deploy map.\n"
    "- **Feeds the capstone:** every service in [`capstone/infra/`](../../../capstone/) assumes a "
    "least-privilege role like the one you wrote here; the Ch 36 Terraform "
    "([`templates/terraform-module/`](../../../templates/terraform-module/)) encodes these policies "
    "as code. See book §33.1 and the §33.9 checklist."
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

out = HERE / "33-01-iam-and-least-privilege.ipynb"
out.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
print("wrote", out, "cells:", len(cells))
