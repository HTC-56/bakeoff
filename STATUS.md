# Status

Repo scaffolded 2026-08-27. Nothing built yet. SPEC.md is the product;
DECISIONS.md locks the fence; ROADMAP.md is the scoreboard. The planning lane
authors Phase A from SPEC.md (Phase A must prove the toolchain — uv, ruff,
mypy --strict, pytest — plus one grader and the bundled stub server
end-to-end before anything else is built; this is the executor's first
Python repo).

Per-phase sections append below as phases ship.

## Phase A

Phase A shipped the toolchain (uv, ruff, mypy --strict, pytest), four graders
(`grade_exact`, `grade_contains`, `grade_regex`, `grade_numeric_tolerance`), the
HTTP seam in the bundled stub server (including the `error_status` switch),
`scrub-check.sh`, CI, `README.md`, and `verify.sh`. Still missing: the audition
manifest, the bar and freeze mechanic, the runner, the report, the CLI.

## Phase B

Phase B shipped the audition manifest (`Audition` dataclass, `load_audition`, bar model
with per-pair overrides), task suites as files (five grader spec classes and the
`run_grader` dispatch), the fifth grader (`grade_json_schema`), the quickstart example
under `examples/quickstart`, and validation-error tests in
`TestManifestErrors` and `TestSuiteErrors`. Still missing: the freeze/lockfile and
REBARRED mechanic, the runner, the report, the CLI, `docs/PROCESS.md`.

## Phase C

Phase C shipped the runner (`runner.py`: retries, backoff, per-candidate concurrency,
error outcomes), the malformed stub reply, `summarize`, `judge`, and `exit_code` in
`scoring.py`, the JSONL run ledger (`ledger.py`), and end-to-end proofs against the
bundled stub. Still missing: the freeze/lockfile and REBARRED mechanic, the report,
the CLI, `docs/PROCESS.md`.

## Phase D

Phase D shipped the freeze module (`freeze.py`: bar hashing, `Lockfile` model, read/write,
`FreezeStatus`/`FreezeCheck` shapes), the freeze check (`check_freeze`), its run gate
(`require_freeze` with `--rebar`), the quickstart lockfile (`audition.lock`), the bar hash
recorded in the ledger per run, and a REBARRED end-to-end proof in
`TestRebarredEndToEnd`. Still missing: the report, the CLI, `docs/PROCESS.md`.

## Phase E

Phase E shipped the report module (`report.py`: `results.json` read/write, the
self-contained HTML page with freeze banner and scoreboard, the per-case drill-down,
the spend table with p50/p95/slowest latency), the REBARRED branding proof in
`TestRebarredReport`, the self-containment assertion in `TestSelfContained`, and the
end-to-end pipeline test `TestReportEndToEnd`. Still missing: the CLI and
`docs/PROCESS.md`.
