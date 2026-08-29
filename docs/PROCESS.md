# PROCESS.md — how this repo got built

## The shape of the loop

A planning lane writes a phase spec (`TASK_PHASE_*.md`) and a checklist
(`TODO.md`). A local model works the first unchecked task, one task per
session, and must leave either a commit or a `BLOCKED.md`. The gates in
`verify.sh` are what "done" means — no task lands red.

Every session runs the same five gates plus `scrub-check.sh` (public-repo
discipline) and a README-quickstart lint:

```
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
bash scripts/scrub-check.sh
bash scripts/readme-lint.sh
```

Six gates. Six passes. A task lands only when all six are green.

## What shipped, phase by phase

- **Phase A** — toolchain (uv, ruff, mypy --strict, pytest), four graders
  (`exact`, `contains`, `regex`, `numeric_tolerance`), the HTTP seam in the
  bundled stub server, `scrub-check.sh`, CI, `README.md`, and `verify.sh`.

- **Phase B** — the audition manifest (`Audition` dataclass, `load_audition`, bar
  model with per-pair overrides), task suites as files (five grader spec classes
  and the `run_grader` dispatch), the fifth grader (`json_schema`), the
  quickstart example, and validation-error tests.

- **Phase C** — the runner (retries, backoff, per-candidate concurrency, error
  outcomes), the malformed stub reply, `summarize`/`judge`/`exit_code` in
  `scoring.py`, the JSONL run ledger, and end-to-end proofs against the bundled
  stub.

- **Phase D** — the freeze module (bar hashing, `Lockfile` model, read/write,
  `FreezeStatus`/`FreezeCheck` shapes), the freeze check (`check_freeze`), its
  run gate (`require_freeze` with `--rebar`), the quickstart lockfile, the bar
  hash recorded in the ledger per run, and a REBARRED end-to-end proof.

- **Phase E** — the report module (`results.json` read/write, the self-contained
  HTML page with freeze banner and scoreboard, per-case drill-down, spend table
  with p50/p95/slowest latency), the REBARRED branding proof, the
  self-containment assertion, and the end-to-end pipeline test.

- **Phase F** — the CLI (click group with `init`, `validate`, `freeze`, `run`,
  `report` commands), the scaffold templates for quickstart auditions, the
  rewritten README with quickstart and freeze-mechanic sections, the README
  quickstart lint gate, and this page.

## The evidence

This repo has 78 commits.

```
41f069d feat(F5): rewrite README Status, add Quickstart and Freeze mechanic sections
461c25a feat(F3): add templates.py with write_scaffold and TestWriteScaffold
191e409 feat(F2): add the freeze command to cli.py with TestFreezeCommand
89acf4c feat(F1): add the validate command to cli.py with TestValidateCommand
d5ad3d8 feat(F0): the CLI seam plus the run and report commands
80ee6eb feat(E6): close Phase E — append STATUS.md §E, update ROADMAP.md rows 6/9 + reservations ledger
bf751f7 feat(E2): the spend table — _spend section + TestSpend tests
d709493 plan: Phase E — the report
1da1aca feat(E0): the report — results.json plus a self-contained HTML render
9d48006 feat(D6): close Phase D — append STATUS.md §D, update ROADMAP.md rows 4/9 + reservations ledger
2e9918b feat(C3): add judge(summaries, bar) and exit_code(verdicts) to scoring.py
8fb2a0e feat(C2): add summarize(outcomes) to scoring.py with TestSummarize
4405479 plan: Phase C — the runner
2631eae feat(C0): the async runner — retries, backoff, per-candidate concurrency, usage capture
3af98ec plan: Phase B — the audition on disk
62ca700 feat(B0): the audition manifest — pydantic models, bar, load_manifest
0f21909 plan: Phase A — prove the stack, finish the graders and the stub
83441ff feat(A0): toolchain scaffold — uv, ruff, mypy --strict, pytest, src layout
7d36b97 scaffold: spec, decisions, loop contract, scoreboard
```

Every `feat()` commit was preceded by a `plan:` commit that authored the phase
spec and the task list. `chore(loop): sweep-commit` rounds out each task when
stranded work remains after the main submission.

## The split

The hard module of each phase (`§A0`, `§B0`, `§C0`, `§D0`, `§E0`, `§F0`) was
written by the planning model and committed before the task list for that phase
existed. The numbered tasks were carried by the local model — the same model
writing this page.

This is not a separation of concerns; it is a separation of turns. The planning
model sets the architecture and the executor proves it.

## What is not proven

Every number in this repo comes from the bundled stub. No real endpoint has been
audited. `scripts/live-check.sh` is a human's job.
