# Sample Risk Playbook & Standard Clause Library

> **This is a synthetic teaching artifact, not legal advice.** It exists so the demo has a
> grounded corpus to retrieve over. Replace every rule below with *your firm's* negotiated
> positions and standard templates before using anything like this for real review.

Each rule has a stable `RULE-ID` (cited verbatim in every flag), a clause type, a severity, the
standard (fallback) position, and what to watch for. The retrieval layer (`rag-pipeline`) indexes
these so a flag is always grounded in a specific rule — **no uncited flags**.

---

## RULE-LIAB-001 — Limitation of Liability (liability) — severity: high
Standard position: liability is **capped at fees paid in the trailing 12 months**, and both
parties exclude indirect/consequential damages. Watch for **uncapped liability**, "unlimited
liability", or a cap far above 12 months' fees. An uncapped liability clause is a high-severity
deviation that must go to counsel before signature.
Standard template: "Each party's total aggregate liability under this Agreement shall not exceed
the fees paid in the twelve (12) months preceding the claim."

## RULE-INDEM-001 — Indemnification (indemnification) — severity: high
Standard position: indemnities are **mutual** and **scoped** to third-party claims arising from
breach, IP infringement, or gross negligence. Watch for **one-sided** indemnities, indemnities
with **no cap**, or a duty to "defend" without control of defense. A one-way uncapped indemnity is
a high-severity deviation.

## RULE-TERM-001 — Termination (termination) — severity: medium
Standard position: either party may terminate **for convenience on 30 days' written notice**, and
**for cause on 30 days' notice with a cure period**. Watch for notice periods **shorter than 30
days**, termination for convenience available to **only one** party, or **auto-renewal** without an
opt-out window.

## RULE-CONF-001 — Confidentiality (confidentiality) — severity: medium
Standard position: mutual confidentiality with a **defined term (3–5 years)** post-termination and
standard carve-outs (publicly known, independently developed, compelled by law). Watch for a
**perpetual** confidentiality obligation, missing carve-outs, or a one-way NDA where mutual is
expected.

## RULE-PAY-001 — Payment Terms (payment_terms) — severity: low
Standard position: **Net 30** from a valid invoice; late fees the lesser of 1.5%/month or the legal
maximum. Watch for **Net 60/Net 90** (cash-flow risk), **payment in advance** of delivery, or no
late-fee remedy.

## RULE-LAW-001 — Governing Law (governing_law) — severity: low
Standard position: governed by the laws of **[Your State]**, venue in **[Your County]**. Watch for a
**foreign jurisdiction**, a forum far from the company, or mandatory arbitration in an
inconvenient venue.

## RULE-WARR-001 — Warranty (warranty) — severity: medium
Standard position: services warranted to conform to documentation for **90 days**; limited remedy is
re-performance. Watch for **"AS IS" / no warranty** where a conformance warranty is expected, or an
open-ended warranty with no time limit.

## RULE-IP-001 — IP Ownership (ip_ownership) — severity: high
Standard position: each party **retains its pre-existing IP**; deliverables' IP assigns to the
customer **on full payment**; vendor keeps a license to its tools/know-how. Watch for an
**assignment of all IP including pre-existing/background IP**, or ownership transferring **before**
payment.

## RULE-DATA-001 — Data Protection (data_protection) — severity: high
Standard position: a **DPA** governs personal data, processing is limited to documented
instructions, sub-processors require notice, and breach notification is **within 72 hours**. Watch
for **no DPA**, unrestricted sub-processing, data transfer outside approved regions, or a breach-
notice window **longer than 72 hours**.

---

## How a flag cites this

A flag names the deviating clause, the matched `RULE-ID`, the rule's severity, and the standard
position — so a reviewer can jump from "flag" to "the exact playbook rule it came from" in one hop.
Uncited = failure (PLAN.md, Phase-2 definition of done).
