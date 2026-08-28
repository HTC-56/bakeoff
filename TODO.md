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
- [ ] §A5 — Write `README.md` (what bakeoff is, honest status, uv setup, gates, running
  the stub) and add `readme = "README.md"` to `pyproject.toml`. Gate: §A0.
- [ ] §A6 — Write `verify.sh` composing the five gates, run it, then append a Phase A
  section to `STATUS.md` and update rows 3, 5, 8, 9 plus the reservations ledger in
  `ROADMAP.md`. Gate: `bash verify.sh` green.
