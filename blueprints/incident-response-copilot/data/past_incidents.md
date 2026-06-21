# Past incidents (institutional memory)

These are short snippets from resolved incidents. The copilot retrieves them alongside runbooks
because "we have seen this before, here is what fixed it" is often the single most useful signal
during triage. Each block is one incident, separated by a `---` line.

INC-204: checkout 5xx spike after deploy v2.7.0
Severity: SEV1. checkout error_rate jumped to ~40% within 8 minutes of deploy v2.7.0 landing.
Logs were full of `HikariPool-1 - Connection is not available` and `pool exhausted`. The new
build added a synchronous call to payments inside the request path, draining the connection
pool. Mitigation: rolled checkout back from v2.7.0 to v2.6.4 (approved by on-call). Recovery in
~3 minutes. Follow-up: move the payments call off the hot path, add a pool-saturation alert.

---

INC-187: payments latency from slow card processor
Severity: SEV2. payments p99 climbed to ~2s; checkout began timing out as a knock-on effect.
payments error_rate stayed near baseline — the tell that the root cause was downstream, not in
payments itself. Logs showed `upstream ... timeout`. A restart would have dropped in-flight
charges, so we did NOT restart; we shed load and escalated to the processor. Resolved when the
processor recovered. Lesson: latency with flat error_rate => look downstream before acting.

---

INC-203: checkout connection pool wedged, no recent deploy
Severity: SEV2. checkout errors with `pool exhausted` but `list_deploys` showed no deploy in the
prior hour. With no correlated deploy and a clearly wedged pool, the fix was a state-clearing
**restart** (approved), not a rollback. Recovered immediately. Lesson: restart clears wedged
state; rollback fixes regressions — pick by whether a deploy correlates.

---

INC-160: search slow queries during index rebuild
Severity: SEV3. search p99 elevated with `slow query` and `index refreshed` log lines. No
customer-blocking errors. We watched rather than acted; latency self-healed as the index refresh
completed. Lesson: not every degradation needs a mutating action — search degradation is rarely
deploy-caused.
