# data/redteam — SAFE red-team fixtures (Ch 41)

These files are a **benign, labeled** corpus used to verify *our own* guardrails.
Every "attack" payload is obviously fake (`evil.example`) and targets no real
system or model. The deliverable in every notebook is the **measured defense**
(attack-success-rate, guard flags, contained blast radius) — never an attack.

- `injection_cases.json` — direct + indirect + lethal-trifecta exfil cases, each
  with the `fail_if` outcome that would count as a defense failure.
- `exfil_document.txt` — one end-to-end fake-exfil document (an "attachment").
- `pii_samples.json` — benign strings carrying **fake** PII to exercise redaction.
