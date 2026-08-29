# Loop tasks

Ordered; each is one short session. Work the first unchecked box. Each task is
fully specced in ONE greppable section of its phase doc (`TASK_PHASE_A.md` §A1,
§A2, …) — grep your section, read it, build it.

*(no tasks yet — the planning lane authors Phase A from SPEC.md)*

## Phase A: prove the stack, finish the graders and the stub — see TASK_PHASE_A.md

The foundation is already committed (`feat(A0)`: toolchain, `graders.py` with
`grade_exact`, the `client.py` seam, `stub.py`, `scrub-check.sh`, CI). Read
**§A0 in TASK_PHASE_A.md first** — it holds the gate command and the typing rules
every task below assumes. Then grep your own section and build it.

- [x] §A1 — Add `grade_contains` to `src/bakeoff/graders.py`, mirroring `grade_exact`;
  new `TestGradeContains` in `tests/test_graders.py`. Gate: §A0's five commands.
- [x] §A2 — Add `grade_regex` to `src/bakeoff/graders.py`; a pattern that will not
  compile raises `GraderConfigError`. Tests in `tests/test_graders.py`. Gate: §A0.
- [x] §A3 — Add `grade_numeric_tolerance` to `src/bakeoff/graders.py`; non-numeric
  completion fails, negative tolerance raises. Tests in `tests/test_graders.py`. Gate: §A0.
- [x] §A4 — Add `error_status` to `src/bakeoff/stub.py` and wire it into `do_POST` so a
  `status:503:` prompt returns that HTTP code. Tests in `tests/test_stub_end_to_end.py`.
  Gate: §A0.
- [x] §A5 — Write `README.md` (what bakeoff is, honest status, uv setup, gates, running
  the stub) and add `readme = "README.md"` to `pyproject.toml`. Gate: §A0.
- [x] |- §A6 — Write `verify.sh` composing the five gates, run it, then append a Phase A
  section to `STATUS.md` and update rows 3, 5, 8, 9 plus the reservations ledger in
  `ROADMAP.md`. Gate: `bash verify.sh` green.

## Phase B: the audition on disk — see TASK_PHASE_B.md

The two hard modules are already committed (`feat(B0)`): `src/bakeoff/manifest.py`
(the audition manifest + the bar model) and `src/bakeoff/suite.py` (case files and
the five grader specs), plus `src/bakeoff/errors.py`. Read **§B0 in TASK_PHASE_B.md
first** — it holds the gate, the typing rules, and an index of what B0 gives you.
Then grep your own section and build it.

- [x] §B1 — Add `grade_json_schema` to `src/bakeoff/graders.py`, mirroring
  `grade_numeric_tolerance`; a malformed schema raises `GraderConfigError`. Tests in
  `tests/test_graders.py`. Gate: §B0's five commands.
- [x] §B2 — Add `run_grader(spec, completion)` to `src/bakeoff/suite.py`: one
  `isinstance` branch per grader spec, calling its grader. Tests in
  `tests/test_suite.py`. Gate: §B0.
- [x] §B3 — Add the `Audition` dataclass and `load_audition` to
  `src/bakeoff/manifest.py`, loading every suite the manifest names. Tests in
  `tests/test_manifest.py`. Gate: §B0.
- [x] §B4 — Write `examples/quickstart/audition.yaml` and five case files under
  `examples/quickstart/suites/smoke/`, one per grader kind, all passing against the
  bundled stub. New `tests/test_examples.py`. Gate: §B0.
- [x] §B5 — Assert the validation promise: `TestManifestErrors` in
  `tests/test_manifest.py` and `TestSuiteErrors` in `tests/test_suite.py`. Tests
  only, no source changes. Gate: §B0.
- [x] |- §B6 — Run `bash verify.sh`, then append a Phase B section to `STATUS.md` and
  update rows 1-4 plus the reservations ledger in `ROADMAP.md`. Gate: `bash verify.sh`
  green.

## Phase C: the runner — see TASK_PHASE_C.md

The hard module is already committed (`feat(C0)`): `src/bakeoff/runner.py` (retries,
backoff, per-candidate concurrency, errors as outcomes) and `src/bakeoff/scoring.py`
(`percentile` plus the `PairSummary`/`PairVerdict` shapes). Read **§C0 in
TASK_PHASE_C.md first** — gate, typing rules, and an index of what C0 gives you. Then
grep your own section and build it.

- [x] §C1 — Add `malformed_reply` to `src/bakeoff/stub.py` and wire it into `do_POST`, so a
  `malformed:` prompt returns HTTP 200 with a body that is not a chat completion. Tests in
  `tests/test_stub_end_to_end.py`. Gate: §C0's five commands.
- [x] §C2 — Add `summarize(outcomes)` to `src/bakeoff/scoring.py`: one `PairSummary` per
  suite x candidate pair. Tests in `tests/test_scoring.py`. Gate: §C0.
- [x] §C3 — Add `judge(summaries, bar)` and `exit_code(verdicts)` to
  `src/bakeoff/scoring.py`, using `Bar.for_pair`. Tests in `tests/test_scoring.py`. Gate: §C0.
- [x] §C4 — Prove the runner against the bundled stub: new `TestRunAuditionEndToEnd` in
  `tests/test_runner.py`, running the quickstart audition plus a 503 and a malformed case.
  Tests only, no source changes. Gate: §C0.
- [x] |- §C5 — Write `src/bakeoff/ledger.py` (`run_record`, `append_run`, `read_ledger`) and
  `tests/test_ledger.py`. One JSON object per line, one line per run. Gate: §C0.
- [x] |- §C6 — Run `bash verify.sh`, then append a Phase C section to `STATUS.md` and update
  row 5, row 9 and the reservations ledger in `ROADMAP.md`. Gate: `bash verify.sh` green.

## Phase D: the freeze — see TASK_PHASE_D.md

The hard module is already committed (`feat(D0)`): `src/bakeoff/freeze.py` (bar hashing,
the `Lockfile` model, read/write, and the `FreezeStatus`/`FreezeCheck` shapes) plus
`tests/test_freeze.py` and its helpers. Read **§D0 in TASK_PHASE_D.md first** — gate,
typing rules, and an index of what D0 gives you. Then grep your own section and build it.

- [x] §D1 — Add `check_freeze(bar, lock)` to `src/bakeoff/freeze.py`, returning a
  `FreezeCheck` with one of the three statuses; `TestCheckFreeze` in
  `tests/test_freeze.py`. Gate: §D0's five commands.
- [x] §D2 — Add `require_freeze(check, *, rebar)` to `src/bakeoff/freeze.py`: raises
  `FreezeError` unless the run may proceed. `TestRequireFreeze` in
  `tests/test_freeze.py`. Gate: §D0.
- [x] §D3 — Generate `examples/quickstart/audition.lock` with the command in §D3 and
  commit it; `TestQuickstartFreeze` in `tests/test_examples.py` asserts the shipped
  lockfile still matches the shipped bar. Gate: §D0.
- [x] §D4 — Give `run_record` in `src/bakeoff/ledger.py` a `freeze` argument and a
  `"freeze"` key, so a run records the bar hash it ran under. `TestRunRecordFreeze` in
  `tests/test_ledger.py`. Gate: §D0.
- [x] |- §D5 — Prove REBARRED on disk: `TestRebarredEndToEnd` in `tests/test_freeze.py`
  freezes a copy of the example manifest, lowers its bar, and asserts the check and the
  gate both catch it. Tests only. Gate: §D0.
- [x] |- §D6 — Run `bash verify.sh`, then append a Phase D section to `STATUS.md` and
  update rows 4 and 9 plus the reservations ledger in `ROADMAP.md`. Gate: `bash verify.sh`
  green.

## Phase E: the report — see TASK_PHASE_E.md

The hard module is already committed (`feat(E0)`): `src/bakeoff/report.py` (the
results document, `results.json` read/write, and the HTML page with header, freeze
banner and scoreboard) plus `tests/test_report.py` and its helpers. Read **§E0 in
TASK_PHASE_E.md first** — gate, typing rules, the `sections` anchor in
`render_report`, and an index of what E0 gives you. Then grep your own section and
build it.

- [x] §E1 — Add `_case_drilldown` to `src/bakeoff/report.py` (one `<details>` per pair,
  the actual completions, escaped) and add it to the `sections` list;
  `TestCaseDrilldown` in `tests/test_report.py`. Gate: §E0's five commands.
- [x] §E2 — Add `_spend` to `src/bakeoff/report.py`: per-candidate token totals plus
  p50/p95/slowest latency from `scoring.percentile`; add it to `sections`. `TestSpend`
  in `tests/test_report.py`. Gate: §E0.
- [x] §E3 — Prove REBARRED branding from a manifest frozen then edited on disk:
  `TestRebarredReport` in `tests/test_report.py`, mirroring `TestRebarredEndToEnd` in
  `tests/test_freeze.py`. Tests only. Gate: §E0.
- [x] §E4 — Assert the report is one self-contained file: no `<script>`, `<link>`,
  `@import`, `url(` or external URL, and a re-render never changes it.
  `TestSelfContained` in `tests/test_report.py`. Tests only. Gate: §E0.
- [x] |- §E5 — New `tests/test_report_end_to_end.py`: run the quickstart audition
  against the bundled stub, write `results.json` + `report.html` into `tmp_path`, and
  assert both. Tests only. Gate: §E0.
- [x] |- §E6 — Run `bash verify.sh`, then append a Phase E section to `STATUS.md` and
  update rows 6 and 9 plus the reservations ledger in `ROADMAP.md`. Gate:
  `bash verify.sh` green.

## Phase F: the CLI — see TASK_PHASE_F.md

The hard module is already committed (`feat(F0)`): `src/bakeoff/cli.py` (the click
group, the `fixable()` error seam, and the `run` and `report` commands) plus
`tests/test_cli.py` and its helpers. Read **§F0 in TASK_PHASE_F.md first** — gate,
typing rules, the exit-code contract, and an index of what F0 gives you. Then grep
your own section and build it.

- [ ] §F1 — Add the `validate` command to `src/bakeoff/cli.py`: print the candidates,
  the suites, the case count and the freeze state, never failing on the freeze.
  `TestValidateCommand` in `tests/test_cli.py`. Gate: §F0's five commands.
- [ ] §F2 — Add the `freeze` command to `src/bakeoff/cli.py`, writing the lockfile
  beside the manifest and saying whether the bar was new, unchanged or moved.
  `TestFreezeCommand` in `tests/test_cli.py`. Gate: §F0.
- [ ] §F3 — Write `src/bakeoff/templates.py` (the quickstart manifest and the five
  case files as constants, plus `write_scaffold`) and `tests/test_templates.py`.
  Content mirrors `examples/quickstart/`. Gate: §F0.
- [ ] §F4 — Add the `init` command to `src/bakeoff/cli.py`, calling `write_scaffold`
  with a `--force` flag. `TestInitCommand` in `tests/test_cli.py`. Gate: §F0.
- [ ] §F5 — Rewrite `## Status` in `README.md` and add `## Quickstart` and `## The
  freeze mechanic` sections; every command shown must really exist. Docs only. Gate:
  `bash verify.sh` green.
- [ ] |- §F6 — Write `scripts/readme-lint.sh` (every `bakeoff` command the README
  shows must exist) and add one `run_gate` line for it to `verify.sh`. Gate:
  `bash verify.sh` reports 6/6.
- [ ] |- §F7 — Write `docs/PROCESS.md`: the loop's shape, one line per phase A–F, the
  real commit count from `git log`, the planner/executor split, and what is not
  proven. Gate: `bash verify.sh` green.
- [ ] |- §F8 — Run `bash verify.sh`, then append a Phase F section to `STATUS.md` and
  flip rows 7, 9 and the `docs/PROCESS.md` row in `ROADMAP.md`, plus the reservations
  ledger. Gate: `bash verify.sh` green.
