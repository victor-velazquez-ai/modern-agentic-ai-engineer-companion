# Sample policy corpus

> This is the **rule each flag must cite**. It is intentionally small and synthetic so the demo
> runs offline and deterministically. Replace it with your real policy/handbook/regulatory
> corpus — the `rag-pipeline` retriever indexes whatever you put here, and every flag the agent
> raises is grounded by retrieving the most relevant rule below.
>
> Format: one rule per `##` heading. The heading id (e.g. `COMM-01`) is what the agent cites; the
> body is what gets retrieved and shown as the basis. Keep each rule self-contained so a single
> retrieved chunk is enough to explain a flag.

## COMM-01 — No sharing of customer PII over unencrypted channels

Customer personally identifiable information (PII) — full names with account numbers, government
IDs, card numbers, dates of birth — must never be sent over email, public chat, or any
unencrypted channel. Mask all but the last four digits of any account or card number. Sharing raw
PII externally is a reportable data-handling violation.

## COMM-02 — No promises of guaranteed investment returns

Employees must not state or imply guaranteed, risk-free, or specific returns to clients ("you will
double your money", "guaranteed 20%", "no risk"). All return discussion must be balanced and
include risk language. Guarantees of performance are a marketing-compliance and suitability
violation.

## COMM-03 — No disclosure of material non-public information (MNPI)

Do not share material non-public information — unannounced earnings, pending mergers or
acquisitions, unreleased financials — outside the need-to-know wall. Discussing MNPI in
non-privileged channels, or hinting at it to enable trading, is an insider-information violation
and must be escalated immediately.

## COMM-04 — No harassment, discrimination, or abusive language

Workplace communications must be professional and respectful. Threats, slurs, sexual harassment,
and discriminatory remarks against any protected class are prohibited. Trust-and-safety reviews
all such reports.

## TXN-01 — Transactions above the reporting threshold require review

Any single transaction at or above the USD 10,000 reporting threshold (or a same-day pattern of
smaller transactions that sums above it) must be reviewed and reported per anti-money-laundering
(AML) obligations. Structuring transactions just under the threshold to avoid reporting is itself
a violation.

## TXN-02 — Sanctioned and high-risk counterparties are prohibited

No transaction may be sent to, or received from, a counterparty on a sanctions list or in a
prohibited jurisdiction. Payments to flagged high-risk entities must be blocked and escalated to
the financial-crime team.

## TXN-03 — Expenses must match policy and have valid documentation

Employee expenses and reimbursements must fall within policy limits, be for legitimate business
purposes, and carry valid receipts/documentation. Duplicate submissions, personal expenses billed
as business, or missing documentation above the receipt threshold are policy violations.

## GEN-01 — Routine business communication (no violation)

Ordinary business communication — scheduling, status updates, public product information, general
pleasantries — is permitted and is **not** a violation. The screener should classify clearly
benign activity as `clear` so reviewers are not buried in false positives.
