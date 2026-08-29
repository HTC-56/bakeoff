# Phase F — the CLI: the thing a user actually types

**ROADMAP row this phase ships:** row 7 (*CLI — init, validate, freeze, run, report*),
which reads NOT BUILT today. It also finishes row 9 (README quickstart) and the
`docs/PROCESS.md` row. No other row is the subject of this phase.

The hard module is already committed (`feat(F0)`): `src/bakeoff/cli.py` holds the click
group, the shared error seam, and the two commands that wire every earlier phase
together — `run` (load → freeze gate → audition → score → results.json + report.html +
ledger line → exit 0/1) and `report` (re-render from results.json). The tasks below add
the three remaining commands, the scaffold `init` writes, the README quickstart that
uses them, the lint that keeps that quickstart honest, and the process story.

## §F0 — house rules for every task in this phase

Read this once; §F1–§F8 assume it.

**The gate** — all five, every task, no exceptions:

```
uv run ruff check . && uv run ruff format --check . && uv run mypy \
  && uv run pytest && bash scripts/scrub-check.sh
```

Red is not done. If `ruff format --check` complains, run `uv run ruff format .`.
`bash verify.sh` runs the same five with a summary.

**Conventions this repo already uses** — mirror them, do not invent:

- `mypy` runs `--strict` over `src/` **and** `tests/`. Every function needs
  annotations, tests included: `def test_something(self) -> None:`. A pytest fixture
  argument needs one too: `def test_x(self, tmp_path: Path) -> None:`. A missing
  `-> None` is the most likely reason your gate goes red.
- Every module starts with a docstring, then `from __future__ import annotations`.
- `pytest.raises(..., match=...)` patterns are regexes: pick a match string with no
  `.`, `(` or `*` in it, or ruff RUF043 will fail you.
- Never add a runtime dependency; never add `# type: ignore`; never loosen a ruff or
  mypy setting. A task that genuinely cannot pass strict typing is a BLOCKED.md.
- Line length 100.

**The rule every command in this phase must keep:** exit codes carry meaning. `0` the
command worked, `1` only ever means `run` finished and a pair missed the bar, `2` the
audition is misconfigured. Never print a traceback at a user — wrap loading in the
`fixable()` seam below and the loader's own message becomes the output.

**What F0 already gives you** (grep `src/bakeoff/cli.py`, do not read it whole):

- `main` — the click group every command hangs off. A new command is
  `@main.command()` plus a function; nothing else in the file changes.
- `_MANIFEST_ARGUMENT` — the positional `[MANIFEST]` argument (defaults to
  `audition.yaml`, comes in as a `Path`). Apply it as a decorator; do not retype it.
- `fixable()` — a context manager that re-raises any `ConfigError` as a `CliError`,
  which click prints as `Error: <message>` and exits 2. Every loader in this repo
  raises a `ConfigError` subclass, so `with fixable(): ...` is the whole error story.
- `load(manifest)` → the `Audition`, or exit 2. `freeze_state(audition, manifest)` →
  the `FreezeCheck` for the lockfile beside it. `describe_freeze(check)` → one line
  naming the state and the hash(es).
- Constants `DEFAULT_MANIFEST`, `DEFAULT_RESULTS`, `DEFAULT_REPORT`, `CONFIG_EXIT_CODE`.
- Output is written with `click.echo`, never `print`.
- `tests/test_cli.py`: helpers `invoke(*args)` (runs the CLI, returns click's `Result`,
  never raises — `result.output` holds stdout *and* stderr), `copy_quickstart(dest)`,
  `quickstart_against_stub(dest)` (a context manager yielding a manifest pointed at a
  live stub), and `lower_the_bar(manifest)`. Use them; do not build a second harness.

**Commit** the source files you changed, by name. Never `git add .` — the repo has
untracked loop scratch (`.plan-stamps/`, `plan.log`) that must never be committed.

## §F1 — the `validate` command: say what is in this audition

**Files:** `src/bakeoff/cli.py` (add one command; put it above `run`) and
`tests/test_cli.py` (append a new class at the end).

**Pattern file:** the `report` command in `src/bakeoff/cli.py` — the smallest command
in the file, and it shows the whole shape: decorators, `with fixable():`, `click.echo`.

SPEC.md feature 7 promises `validate`. It loads the manifest and every suite it names
and prints what it found, so a user can see the audition before spending a single
token on it. Add a `validate` command taking `_MANIFEST_ARGUMENT` that:

- calls `load(manifest)` — a bad manifest therefore prints its own message and exits 2
  without you writing any error handling;
- echoes one line naming the manifest and the totals (candidates, suites, cases);
- echoes one line per candidate with its name, its model, and its `base_url`;
- echoes one line per suite with its name and how many cases it holds (`len(suite)`);
- echoes the freeze state via `freeze_state` + `describe_freeze`, but **never fails on
  it** — an unfrozen manifest is still a valid manifest, and `run` is what enforces
  the freeze. Exit 0.

**Tests** (new class `TestValidateCommand`), using `copy_quickstart`:

1. validating the quickstart manifest exits 0 and its output names `stub` and `smoke`.
2. The output states five cases.
3. The output mentions the freeze state `frozen`.
4. Deleting the lockfile first still exits 0, and the output says `unfrozen`.
5. A manifest path that does not exist exits `CONFIG_EXIT_CODE` and the output holds
   `cannot read manifest` and no `Traceback`.

## §F2 — the `freeze` command: pre-register the bar

**Files:** `src/bakeoff/cli.py` (add one command, below `validate`) and
`tests/test_cli.py` (append a new class at the end).

**Pattern file:** the `validate` command you just wrote in `src/bakeoff/cli.py`.

SPEC.md feature 4: `bakeoff freeze` hashes the bar into a lockfile beside the manifest,
before any model runs. `src/bakeoff/freeze.py` already does the work — grep it for
`lockfile_path`, `freeze_bar` and `write_lockfile`; this command only calls them.

Add a `freeze` command taking `_MANIFEST_ARGUMENT` that:

- loads with `load(manifest)`;
- takes `freeze_state(audition, manifest)` **before** writing, so it can say whether
  this is a first freeze or a re-registration of a bar that had moved;
- builds the lockfile with `freeze_bar(audition.manifest, manifest_path=manifest)` and
  writes it to `lockfile_path(manifest)`;
- echoes the lockfile path and the new bar hash, plus one word for which of the three
  cases it was: a bar that was already frozen and unchanged, a bar frozen for the
  first time, or a moved bar now re-registered. Exit 0.

Re-freezing is always allowed: deliberately re-registering a new bar is the honest
move, and the report brands any *run* that happens under a stale freeze.

**Tests** (new class `TestFreezeCommand`), using `copy_quickstart`:

1. After deleting the copied lockfile, `freeze` exits 0 and the lockfile exists again.
2. That written lockfile makes `check_freeze` report `FreezeStatus.FROZEN` (import
   from `bakeoff.freeze`; `tests/test_examples.py` shows the two-line idiom).
3. The output holds `sha256:`.
4. Freezing an already-frozen unchanged bar exits 0 and leaves the same `bar_hash`.
5. After `lower_the_bar(manifest)`, `freeze` exits 0 and the lockfile's `bar_hash`
   differs from the one before.
6. A manifest path that does not exist exits `CONFIG_EXIT_CODE`.

## §F3 — `templates.py`: the scaffold `init` writes

**Files:** new `src/bakeoff/templates.py` and new `tests/test_templates.py`.

**Pattern files:** `examples/quickstart/audition.yaml` and the five case files in
`examples/quickstart/suites/smoke/` — that tree *is* the content. Read those six files
and embed their bodies as string constants. Mirror `tests/test_examples.py`
(`TestQuickstart`) for the test shape.

Why constants rather than copying `examples/` at runtime: `examples/` is not inside
the package, so an installed wheel would not have it. `bakeoff init` must work for a
stranger who ran `uv tool install bakeoff` and never cloned the repo.

Write `src/bakeoff/templates.py` holding:

- `QUICKSTART_MANIFEST: str` — the manifest body. Keep `base_url:
  http://localhost:8000`, which is the stub's documented port.
- `QUICKSTART_CASES: dict[str, str]` — five entries, filename → body, one per grader
  kind, keyed exactly as the files are named today (`01-exact.yaml` … ).
- `class TemplateError(ConfigError)` — import `ConfigError` from `.errors`, mirroring
  how `manifest.py` declares `ManifestError`.
- `write_scaffold(directory: str | Path, *, force: bool = False) -> list[Path]` —
  creates `<directory>/audition.yaml` and `<directory>/suites/smoke/<name>.yaml` for
  every case, creating parent directories, and returns the paths it wrote in that
  order. It raises `TemplateError` naming the first file that already exists, unless
  `force` is true. It writes **no** lockfile: freezing is a separate, deliberate step.

**Tests** (new file, class `TestWriteScaffold`), asserting:

1. Writing into a `tmp_path` returns six paths and all six exist.
2. `load_audition` on the written manifest gives one candidate and one suite of five
   cases, with five distinct grader kinds.
3. Every written case passes: for each case, `run_grader(case.grader,
   canned_reply(case.prompt))` is passed — the same idiom as
   `test_every_case_passes_against_the_bundled_stub`.
4. No `audition.lock` is written.
5. Writing twice raises `TemplateError`, and `force=True` succeeds instead.

## §F4 — the `init` command: a working audition in one word

**Files:** `src/bakeoff/cli.py` (add one command, above `validate`) and
`tests/test_cli.py` (append a new class at the end).

**Pattern file:** the `freeze` command in `src/bakeoff/cli.py`.

SPEC.md feature 7: `init` writes a working example manifest and suite. §F3 already did
the writing — this command is the doorway. Add an `init` command that:

- takes a positional `[DIRECTORY]` argument defaulting to `.`, typed
  `click.Path(file_okay=False, path_type=Path)`;
- takes a `--force` flag whose help says it overwrites existing files;
- calls `write_scaffold(directory, force=force)` inside `with fixable():`, so an
  existing scaffold prints its message and exits 2;
- echoes one line per written path, then a closing line telling the user the next two
  commands to type (`bakeoff freeze` and `bakeoff run`). Exit 0.

**Tests** (new class `TestInitCommand`):

1. `init` into a `tmp_path` subdirectory exits 0 and `audition.yaml` exists there.
2. The output names `freeze` and `run` as the next steps.
3. Running `init` twice exits `CONFIG_EXIT_CODE` and the output says the file exists.
4. `init --force` over an existing scaffold exits 0.
5. End to end: after `init` into a directory, `freeze` on that manifest then
   `validate` both exit 0. (Do not `run` it here — that needs a stub; §F0's
   `quickstart_against_stub` covers the run path already.)

## §F5 — the README quickstart: a stranger gets a report in two minutes

**Files:** `README.md` only.

**Pattern file:** the current `README.md` — keep its heading style and its
`## Development` and `## Running the bundled stub` sections as they are.

SPEC.md feature 9 promises a README quickstart, and feature 8 says it audits the
bundled stub so a stranger sees a real report with nothing installed but Python.
Rewrite the `## Status` section and add a `## Quickstart` section above `## Development`.

The quickstart is a fenced block of commands that must all really work, in this order:
`uv sync`; start the stub in a second terminal with `uv run python -m bakeoff.stub
--port 8000`; `uv run bakeoff init myaudition`; `uv run bakeoff freeze
myaudition/audition.yaml`; `uv run bakeoff run myaudition/audition.yaml`; then open the
`report.html` it wrote. Say in one line what each step does.

Then a `## The freeze mechanic` section demonstrating the honesty story: edit
`min_pass_rate` in the manifest after freezing, re-run, and show that the run is
refused with exit 2; re-run with `--rebar` and the report is branded REBARRED with
both hashes. This is the product's whole point — show it, do not describe it.

Rewrite `## Status` honestly: the CLI, the graders, the runner, the freeze mechanic and
the report are built and gated against the bundled stub. Two things are not: the hero
screenshot (it needs a human with a browser) and any claim that a real, non-stub
endpoint was audited — `scripts/live-check.sh` is run by a human, not by CI. Do not
imply either has happened.

**Constraints:** every command you write must exist — §F6 adds a gate that checks this.
Addresses are `localhost` only. No screenshot link to a file that does not exist. Run
`bash verify.sh` before committing; there is no new test file for this task.

## §F6 — the README-quickstart lint, the last gate `verify.sh` was promised

**Files:** new `scripts/readme-lint.sh` and one added line in `verify.sh`.

**Pattern file:** `scripts/scrub-check.sh` — copy its skeleton exactly: the `set -uo
pipefail`, the `cd "$(dirname "$0")/.."`, the `fail=0`, the `report()` function that
sets `fail=1` and prints, and the final exit.

§A6 deferred this gate "until the CLI exists". It exists now. SPEC.md's gate line is
`verify.sh` = the five gates + a README-quickstart lint: *the commands shown in the
README must exist in the repo.* Two checks, both against `README.md`:

1. Every `bakeoff <subcommand>` named in the README is a real command. Collect them
   with `grep -oE '\bbakeoff [a-z]+' README.md`, drop duplicates with `sort -u`, and
   for each one check that `uv run bakeoff <subcommand> --help` exits 0. Report the
   subcommand as a finding when it does not. Ignore any word that is a flag.
2. Every `python -m bakeoff.<module>` named in the README names a module that exists —
   check `src/bakeoff/<module>.py` is a file.

Print a clean one-line summary when nothing is found, mirroring scrub-check's last
line. Then add one `run_gate "readme lint" bash scripts/readme-lint.sh` line to
`verify.sh` after the `scrub-check` line.

**Verification for this task:** `bash scripts/readme-lint.sh` exits 0 on the README as
§F5 left it, and `bash verify.sh` reports 6/6 gates passed. There is no new test file.
Sanity-check the lint really bites: temporarily add a line naming a fake command to the
README, confirm the script exits 1, then **restore the README** before committing.

## §F7 — `docs/PROCESS.md`: how this repo got built

**Files:** new `docs/PROCESS.md` only.

**Pattern file:** `STATUS.md` — its per-phase sections are the raw material, and its
plain, claim-nothing-extra tone is the register to write in.

SPEC.md feature 9 names `docs/PROCESS.md`, and ROADMAP.md says it is written near the
end, when there is a history to excerpt. One page, no more. Cover, in this order:

- **The shape of the loop.** A planning lane writes a phase spec (`TASK_PHASE_*.md`)
  and a checklist (`TODO.md`); a local model works the first unchecked task, one task
  per session, and must leave either a commit or a `BLOCKED.md`. The gates in
  `verify.sh` are what "done" means — no task lands red.
- **What shipped, phase by phase.** One line per phase A–F. Read the per-phase
  sections of `STATUS.md` and compress each to a sentence; do not invent any.
- **The evidence.** Run `git log --oneline | wc -l` and `git log --oneline` and quote
  the real commit count and a handful of real subject lines. Numbers you did not
  measure do not go in this file.
- **What the split actually was.** The hard module of each phase (`§A0`, `§B0` … `§F0`)
  was written by the planning model and committed before the phase list existed; the
  numbered tasks were carried by the local model. Say this plainly — the honesty of
  the process page is the same honesty the freeze mechanic is about.
- **What is not proven.** Every number in this repo comes from the bundled stub. No
  real endpoint has been audited; `scripts/live-check.sh` is a human's job. Say so.

**Constraints:** public-repo discipline applies — no absolute paths, no private
hostnames, no naming any other local project. `bash scripts/scrub-check.sh` must stay
green (it scans tracked files, so run it after `git add docs/PROCESS.md`).

## §F8 — close the phase

**Files:** `STATUS.md` (append), `ROADMAP.md` (edit rows), `TODO.md` (tick this box).

**Pattern:** the `## Phase E` section of `STATUS.md` and the row edits `§E6` made.

1. Run `bash verify.sh`. All six gates must pass. If any is red, fix it before
   touching the docs.
2. Append a `## Phase F` section to `STATUS.md`, in the voice of `## Phase E`: what
   Phase F shipped (the five CLI commands, the scaffold templates, the README
   quickstart, the readme lint, `docs/PROCESS.md`) and what is still missing. Be
   accurate about what remains: only the README hero screenshot, which needs a human
   with a browser.
3. In `ROADMAP.md`, flip **row 7** (CLI) to `SHIPPED` with phase `F` and a one-line
   note naming the five commands; flip **row 9** to `SHIPPED` with a note that the
   quickstart and the ledger wiring landed with the CLI; flip the **`docs/PROCESS.md`
   row** to `SHIPPED` with phase `F`. Rows 1–6 and 8 are already SHIPPED — leave them.
4. Add to the reservations ledger in `ROADMAP.md`: the `bakeoff` exit-code contract
   (0 worked / 1 the bar was missed / 2 the audition is misconfigured, §F0); that
   `init` writes no lockfile because freezing is a deliberate separate step (§F3); and
   that the README hero screenshot is the one open item and is human-gated.
