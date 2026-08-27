# Roadmap — the v1 scoreboard

One row per SPEC.md feature. The planning lane keeps status current; row edits here
are the one permitted exception to append-only docs.

| # | Feature (SPEC.md) | Status | Phase | Note |
|---|---|---|---|---|
| 1 | Audition manifest (YAML, pydantic-validated) | NOT BUILT | — | |
| 2 | Task suites as files | NOT BUILT | — | |
| 3 | Pure graders (exact, contains, regex, json-schema, numeric-tolerance) | NOT BUILT | — | |
| 4 | Pre-registered bar + freeze/REBARRED mechanic | NOT BUILT | — | centerpiece |
| 5 | Runner (async httpx, retries, concurrency, usage capture) | NOT BUILT | — | |
| 6 | Report (self-contained HTML + results.json + exit code) | NOT BUILT | — | hero screenshot |
| 7 | CLI (init, validate, freeze, run, report) | NOT BUILT | — | |
| 8 | Bundled stub OpenAI-compatible server | NOT BUILT | — | CI + quickstart engine |
| 9 | Deploy-grade packaging (pyproject, CI, quickstart, ledger) | NOT BUILT | — | live-check.sh not in CI |
| — | docs/PROCESS.md (the loop story) | NOT BUILT | — | written near the end, when there is a ledger to excerpt |

When every row reads SHIPPED and verify.sh is green, the project is done — the
planning lane declares PROJECT SPEC COMPLETE rather than inventing scope.

## Reservations ledger — small deferred calls recorded inside phase specs

*(empty at scaffold; each entry names its home)*
