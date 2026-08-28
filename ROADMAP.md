# Roadmap — the v1 scoreboard

One row per SPEC.md feature. The planning lane keeps status current; row edits here
are the one permitted exception to append-only docs.

| # | Feature (SPEC.md) | Status | Phase | Note |
|---|---|---|---|---|
| 1 | Audition manifest (YAML, pydantic-validated) | NOT BUILT | — | |
| 2 | Task suites as files | NOT BUILT | — | |
| 3 | Pure graders (exact, contains, regex, json-schema, numeric-tolerance) | IN PROGRESS | A | exact shipped (A0); contains/regex/numeric-tolerance in §A1–§A3 |
| 4 | Pre-registered bar + freeze/REBARRED mechanic | NOT BUILT | — | centerpiece |
| 5 | Runner (async httpx, retries, concurrency, usage capture) | NOT BUILT | A | client.py seam shipped in A0; the runner itself is pending |
| 6 | Report (self-contained HTML + results.json + exit code) | NOT BUILT | — | hero screenshot |
| 7 | CLI (init, validate, freeze, run, report) | NOT BUILT | — | |
| 8 | Bundled stub OpenAI-compatible server | IN PROGRESS | A | canned replies + usage green end-to-end (A0); error switch in §A4 |
| 9 | Deploy-grade packaging (pyproject, CI, quickstart, ledger) | IN PROGRESS | A | pyproject/uv, ruff+mypy+pytest, scrub-check, CI shipped (A0); live-check.sh not in CI |
| — | docs/PROCESS.md (the loop story) | NOT BUILT | — | written near the end, when there is a ledger to excerpt |

When every row reads SHIPPED and verify.sh is green, the project is done — the
planning lane declares PROJECT SPEC COMPLETE rather than inventing scope.

## Reservations ledger — small deferred calls recorded inside phase specs

*(empty at scaffold; each entry names its home)*
