# Architecture Decision Records

This directory holds the project's **Architecture Decision Records (ADRs)** — one Markdown
file per significant, hard-to-reverse decision. New here? Read
[`../../README.md`](../../README.md) for the *why* and the workflow; this file is just the
**index**.

## How to add an ADR

1. Copy the blank template: `cp 0000-adr-template.md 000N-<kebab-title>.md`
   (use the next free number; numbers are never reused).
2. Fill in every `▢` / `<…>` placeholder — **including** the *Alternatives considered* section.
3. Add a row to the table below.
4. Commit the ADR **with the change it describes**.

> ADRs are **immutable**: don't edit an Accepted record to change a decision — write a new ADR
> and mark the old one `Superseded by ADR-XXXX`.

## Index

| #    | Title                                                                 | Status   | Date       |
|------|-----------------------------------------------------------------------|----------|------------|
| 0001 | [Record architecture decisions](0001-example-record-architecture-decisions.md) | Accepted | 2025-01-01 |
<!-- ▢ TODO: add a row per ADR. Newest at the bottom; keep numbers monotonically increasing. -->

<!--
  Status legend:  Proposed · Accepted · Superseded by ADR-XXXX · Deprecated
  The 0001 row above is the shipped example — replace or extend it with your own records.
-->
