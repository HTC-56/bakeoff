# Roadmap — the v1 scoreboard

One row per SPEC.md feature. The planning lane keeps status current; row edits here
are the one permitted exception to append-only docs.

| # | Feature (SPEC.md) | Status | Phase | Note |
|---|---|---|---|---|
| 1 | Audition manifest (YAML, pydantic-validated) | NOT BUILT | — | |
| 2 | Task suites as files | NOT BUILT | — | |
| 3 | Pure graders (exact, contains, regex, json-schema, numeric-tolerance) | PARTIAL | A | exact, contains, regex, numeric-tolerance shipped; json-schema pending |
| 4 | Pre-registered bar + freeze/REBARRED mechanic | NOT BUILT | — | centerpiece |
| 5 | Runner (async httpx, retries, concurrency, usage capture) | NOT BUILT | A | client seam shipped in A; runner itself pending |
| 6 | Report (self-contained HTML + results.json + exit code) | NOT BUILT | — | hero screenshot |
| 7 | CLI (init, validate, freeze, run, report) | NOT BUILT | — | |
| 8 | Bundled stub OpenAI-compatible server | SHIPPED | A |
| 9 | Deploy-grade packaging (pyproject, CI, quickstart, ledger) | PARTIAL | A | pyproject, CI, scrub-check, verify.sh, README shipped; ledger and quickstart pending |
| — | docs/PROCESS.md (the loop story) | NOT BUILT | — | written near the end, when there is a ledger to excerpt |

When every row reads SHIPPED and verify.sh is green, the project is done — the
planning lane declares PROJECT SPEC COMPLETE rather than inventing scope.

## Reservations ledger — small deferred calls recorded inside phase specs

*(empty at scaffold; each entry names its home)*

- README-quickstart lint deferred out of `verify.sh` until the CLI exists (§A6).
- json-schema grader deferred out of Phase A (§A3).
