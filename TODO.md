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

- [ ] §C1 — Add `malformed_reply` to `src/bakeoff/stub.py` and wire it into `do_POST`, so a
  `malformed:` prompt returns HTTP 200 with a body that is not a chat completion. Tests in
  `tests/test_stub_end_to_end.py`. Gate: §C0's five commands.
- [ ] §C2 — Add `summarize(outcomes)` to `src/bakeoff/scoring.py`: one `PairSummary` per
  suite x candidate pair. Tests in `tests/test_scoring.py`. Gate: §C0.
- [ ] §C3 — Add `judge(summaries, bar)` and `exit_code(verdicts)` to
  `src/bakeoff/scoring.py`, using `Bar.for_pair`. Tests in `tests/test_scoring.py`. Gate: §C0.
- [ ] §C4 — Prove the runner against the bundled stub: new `TestRunAuditionEndToEnd` in
  `tests/test_runner.py`, running the quickstart audition plus a 503 and a malformed case.
  Tests only, no source changes. Gate: §C0.
- [ ] §C5 — Write `src/bakeoff/ledger.py` (`run_record`, `append_run`, `read_ledger`) and
  `tests/test_ledger.py`. One JSON object per line, one line per run. Gate: §C0.
- [ ] |- §C6 — Run `bash verify.sh`, then append a Phase C section to `STATUS.md` and update
  row 5, row 9 and the reservations ledger in `ROADMAP.md`. Gate: `bash verify.sh` green.
