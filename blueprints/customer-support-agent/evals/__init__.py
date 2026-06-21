"""The eval that gates this solution: a golden set + a resolution grader + a CI gate.

The eval set is the contract (PLAN.md): every prompt/model change must clear it before it ships,
and the headline metric is **resolution** (did the agent take the *right* action, grounded when
it answered) — *not* deflection rate, which rewards an agent for answering tickets it should have
escalated. See :mod:`evals.run_eval`.
"""
