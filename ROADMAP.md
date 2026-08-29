# Roadmap — the v1 scoreboard

One row per SPEC.md feature. The planning lane keeps status current; row edits here
are the one permitted exception to append-only docs.

| # | Feature (SPEC.md) | Status | Phase | Note |
|---|---|---|---|---|
| 1 | Audition manifest (YAML, pydantic-validated) | SHIPPED | B | |
| 2 | Task suites as files | SHIPPED | B | |
| 3 | Pure graders (exact, contains, regex, json-schema, numeric-tolerance) | SHIPPED | B | all five shipped; run_grader dispatches a case spec to its grader |
| 4 | Pre-registered bar + freeze/REBARRED mechanic | SHIPPED | D | bar model and per-pair thresholds shipped in B; bar hashing, the lockfile and the three freeze states shipped in D0; the freeze check, the `--rebar` gate and the quickstart lockfile shipped in D1–D3; REBARRED end-to-end proof in D5; the report's REBARRED branding lands with the report |
| 5 | Runner (async httpx, retries, concurrency, usage capture) | SHIPPED | C | `runner.py` shipped in C0; stub-backed end-to-end proof is §C4; JSONL ledger is §C5 |
| 6 | Report (self-contained HTML + results.json + exit code) | SHIPPED | E | `report.py` shipped in E0: the results document, `results.json` read/write, and the HTML page with the freeze banner and the scoreboard; the per-case drill-down is §E1, the spend table is §E2, the REBARRED branding proof is §E3, the self-containment assertion is §E4, and the end-to-end pipeline test is §E5; the README hero screenshot still needs a human with a browser |
| 7 | CLI (init, validate, freeze, run, report) | PARTIAL | F | `cli.py` shipped in F0: the click group, the `fixable()` error seam, the exit-code contract (0 worked / 1 bar missed / 2 misconfigured), and the `run` and `report` commands — `run` also wires the ledger; `validate` is §F1, `freeze` is §F2, the scaffold templates are §F3 and `init` is §F4 |
| 8 | Bundled stub OpenAI-compatible server | SHIPPED | A |
| 9 | Deploy-grade packaging (pyproject, CI, quickstart, ledger) | PARTIAL | F | pyproject, CI, scrub-check, verify.sh, README shipped; JSONL ledger shipped in C and wired to `bakeoff run` in F0; the `bakeoff` entry point shipped in F0; the README quickstart is §F5 and the README-quickstart lint §A6 deferred is §F6 |
| — | docs/PROCESS.md (the loop story) | PARTIAL | F | written in §F7, now that there is a six-phase history to excerpt |

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
- The freeze hashes the *bar alone*, not the whole manifest: adding a candidate or a
  case is ordinary work and must not invalidate a pre-registration, while moving a
  threshold must (§D0).
- The lockfile is YAML and hand-editable on purpose — the hash is the check, so a
  doctored lockfile simply reads as REBARRED (§D0).
- The `--rebar` flag is the CLI's (§D2); `require_freeze` is the gate the CLI will call.
- The report's REBARRED branding is the report phase's work (§D5).
- The report is rendered from `results.json` alone and never re-dates it, so `bakeoff report`
  is a re-render, not a re-run (§E0); wiring the two artefacts to real paths — where
  `results.json` and `report.html` get written, and the `--rebar` flag — belongs to the CLI
  phase (§E5).
