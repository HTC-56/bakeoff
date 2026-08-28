# Roadmap — the v1 scoreboard

One row per SPEC.md feature. The planning lane keeps status current; row edits here
are the one permitted exception to append-only docs.

| # | Feature (SPEC.md) | Status | Phase | Note |
|---|---|---|---|---|
| 1 | Audition manifest (YAML, pydantic-validated) | SHIPPED | B | |
| 2 | Task suites as files | SHIPPED | B | |
| 3 | Pure graders (exact, contains, regex, json-schema, numeric-tolerance) | SHIPPED | B | all five shipped; run_grader dispatches a case spec to its grader |
| 4 | Pre-registered bar + freeze/REBARRED mechanic | NOT BUILT | B | bar model and per-pair thresholds shipped in B; freeze, lockfile and REBARRED pending |
| 5 | Runner (async httpx, retries, concurrency, usage capture) | PARTIAL | C | `runner.py` shipped in C0; stub-backed end-to-end proof is §C4 |
| 6 | Report (self-contained HTML + results.json + exit code) | NOT BUILT | — | hero screenshot; its scoring input (`scoring.py`, exit code) lands in C |
| 7 | CLI (init, validate, freeze, run, report) | NOT BUILT | — | |
| 8 | Bundled stub OpenAI-compatible server | SHIPPED | A |
| 9 | Deploy-grade packaging (pyproject, CI, quickstart, ledger) | PARTIAL | C | pyproject, CI, scrub-check, verify.sh, README shipped; JSONL ledger is §C5; README quickstart waits on the CLI |
| — | docs/PROCESS.md (the loop story) | NOT BUILT | — | written near the end, when there is a ledger to excerpt |

When every row reads SHIPPED and verify.sh is green, the project is done — the
planning lane declares PROJECT SPEC COMPLETE rather than inventing scope.

## Reservations ledger — small deferred calls recorded inside phase specs

*(empty at scaffold; each entry names its home)*

- README-quickstart lint deferred out of `verify.sh` until the CLI exists (§A6).
- json-schema grader deferred out of Phase A (§A3).
- type-stub dev dependencies (`types-PyYAML`, `types-jsonschema`) added in Phase B because
  neither library ships `py.typed` and mypy --strict is never weakened; runtime dependency
  surface unchanged (§B0).
- The runner measures `latency_ms` as wall time for the whole case *including* retries,
  because that is what a caller of the endpoint actually waited (§C0).
- `scoring.percentile` is nearest-rank, not interpolated, so every number on the report
  is a latency the audition really measured (§C0).
- The run ledger is written but nothing calls it yet; the CLI's `run` command wires it
  up in a later phase (§C5).
