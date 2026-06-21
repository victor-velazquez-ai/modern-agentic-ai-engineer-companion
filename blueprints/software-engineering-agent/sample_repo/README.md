# sample_repo — the agent's target codebase

A deliberately tiny Python library (`textkit`) that stands in for *your* repo. It is the
surface the software-engineering agent reads, tests, and edits. Two jobs are pre-seeded so the
demo has real work to do:

1. **A bug with a failing test.** `textkit.slugify` drops the separator between words, so
   `slugify("Hello World")` returns `"helloworld"` instead of `"hello-world"`. The test in
   `tests/test_slugify.py` is **red**. The `code_agent` reads the failing test, proposes a
   one-line diff, and the `oracle` confirms the suite goes green — *without* the change being
   allowed to "pass" by deleting the assertion.

2. **A deprecated-API migration.** `textkit.legacy_clean()` is deprecated in favour of
   `textkit.normalize()`. Three call sites across `src/` still use the old name. The
   `migrate.py` job rewrites each call site, file by file, behind a resumable manifest, and the
   oracle gates every file.

Nothing here needs installing — the oracle runs the tests in-process. Point the real tool at
*your* repo by swapping this folder and wiring `ci/oracle.py` to your actual test/lint/type
commands (see the blueprint README → "How to adapt it").
