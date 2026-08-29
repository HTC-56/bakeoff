# Phase G — the stranger's path: what a new user actually types

**ROADMAP rows this phase ships:** row 7 (*CLI — init, validate, freeze, run, report*)
and row 9 (*deploy-grade packaging*). The planning lane moved both back from SHIPPED to
PARTIAL on 2026-08-29 for the reasons below. No other row is the subject of this phase.

Why they moved back. The planning lane ran the README quickstart exactly as written,
from a directory that did not exist yet, against a live stub. The first command the
README tells a stranger to type crashed with a Python traceback:

```
$ bakeoff init myaudition
FileNotFoundError: [Errno 2] No such file or directory: '.../myaudition/audition.yaml'
```

Everything after it is sound: freeze, run, the scoreboard, exit codes 0/1/2, and the
whole REBARRED story behave exactly as the README promises. But six green gates and
fourteen test files never caught the crash, because every test writes into pytest's
`tmp_path` — a directory that already exists. No test has ever run the CLI the way a
human runs it.

The second gap: `scripts/live-check.sh`. SPEC.md names it in *Pre-registered rules*, in
*Stack & shape*, and in *Done means*; DECISIONS.md locks it as "the real-endpoint
proof"; README.md tells the reader it is there. The file does not exist.

Phase G closes both — fix the crash, pin the stranger's path with the test that would
have caught it, write the missing script, and finish the README's real-endpoint half.

## §G0 — house rules for every task in this phase

Read this once; §G1–§G8 assume it.

**The gate** — all five, every task, no exceptions:

```
uv run ruff check . && uv run ruff format --check . && uv run mypy \
  && uv run pytest && bash scripts/scrub-check.sh
```

Red is not done. If `ruff format --check` complains, run `uv run ruff format .`.
`bash verify.sh` runs those five plus `readme-lint` and prints `6/6 gates passed`;
the doc tasks below name it as their gate.

**Conventions this repo already uses** — mirror them, do not invent:

- `mypy` runs `--strict` over `src/` **and** `tests/`. Every function needs
  annotations, tests included: `def test_something(self, tmp_path: Path) -> None:`.
  A missing `-> None` is the most likely reason your gate goes red.
- Every module starts with a docstring, then `from __future__ import annotations`.
- `pytest.raises(..., match=...)` patterns are regexes: pick a match string with no
  `.`, `(` or `*` in it, or ruff RUF043 will fail you.
- Never add a runtime dependency; never add `# type: ignore`; never loosen a ruff or
  mypy setting. A task that genuinely cannot pass strict typing is a BLOCKED.md.
- Line length 100. Output is written with `click.echo`, never `print`.

**The stub binds a random port.** `run_stub()` from `bakeoff.stub` is a context manager
yielding a `base_url`. Never bind a fixed port in a test, and never make a network call.

**What the test harness already gives you** (grep `tests/test_cli.py`, do not read it
whole): `invoke(*args)` runs the CLI in-process and returns click's `Result` without
raising — `result.exit_code` and `result.output` (stdout *and* stderr) are what you
assert on. `PLACEHOLDER_URL` is the `http://localhost:8000` string every shipped and
scaffolded manifest carries. `copy_quickstart(dest)`, `quickstart_against_stub(dest)`
and `lower_the_bar(manifest)` are there too. Use them; do not build a second harness.

**Exit codes are the contract:** `0` the command worked, `1` only ever means `run`
finished and a pair missed the bar, `2` the audition is misconfigured.

**Commit** the source files you changed, by name. Never `git add .` — the repo has
untracked loop scratch (`.plan-stamps/`, `plan.log`, `*.log`) that must never be
committed.

## §G1 — the crash: `bakeoff init` into a directory that does not exist

**Files:** `src/bakeoff/templates.py` (one function) and `tests/test_templates.py`
(append one class at the end).

**Pattern file:** `write_scaffold` in `src/bakeoff/templates.py` itself — the
`smoke_dir.mkdir(...)` call a few lines below the bug shows the exact call and flags
this repo uses for making a directory.

`write_scaffold` writes `audition.yaml` into the target directory *before* anything
creates that directory, so `bakeoff init somewhere-new` dies with `FileNotFoundError`
and a traceback. Its own docstring already promises "Creates parent directories as
needed" — make that promise true. The base directory must exist before the manifest is
written, and creating a directory that is already there must stay harmless.

Do not change what the function returns, do not change the order of the six paths, and
do not touch the `TemplateError` behaviour.

**Assertions** (new class in `tests/test_templates.py`, prose — write them yourself):

- `write_scaffold` into a path under `tmp_path` that does not exist returns six paths
  and every one of them exists on disk afterwards.
- The same call two levels deep (e.g. `tmp_path / "a" / "b"`) also works.
- Calling it twice on the same directory without `force` still raises `TemplateError`,
  and the message names `audition.yaml`.
- Calling it twice with `force=True` succeeds and rewrites the six files.

**Gate:** §G0's five commands.

## §G2 — the freeze refusal reads like a typo

**Files:** `src/bakeoff/freeze.py` (the `FreezeError` message inside `require_freeze`)
and `tests/test_freeze.py` (the existing `TestRequireFreeze` class).

The message a user meets when the freeze mechanic fires currently begins:

> `bar rebars since freeze — frozen: sha256:…, current: sha256:…; pass --rebar to proceed`

`rebarred` is the name of a status, not a verb, and this is the exact sentence a user
reads at the moment the product's centerpiece does its job. Reword the first clause so
it reads as plain English — say that the bar has **moved** since its freeze. Keep both
hashes, keep the `pass --rebar to proceed` instruction, and keep it one line.

Do **not** rename `FreezeStatus.REBARRED` or change its `"rebarred"` value: that string
is written into lockfiles, printed by `describe_freeze`, and branded on the report.
Only the sentence in `require_freeze` changes.

Before you commit, `grep -rn "rebars since" tests/ src/` and update every `match=`
pattern and assertion that pinned the old wording — there is at least one in
`tests/test_freeze.py` and there may be one in `tests/test_cli.py`.

**Assertions** (update `TestRequireFreeze`, prose):

- A REBARRED check without `rebar=True` raises `FreezeError` whose message contains
  `moved`, and contains both the frozen and the current hash strings.
- The same message still tells the user to pass `--rebar`.
- A FROZEN check still returns without raising; an UNFROZEN check still raises its own
  "not been pre-registered" message, unchanged.

**Gate:** §G0's five commands.

## §G3 — pin the stranger's path: run the README quickstart in a test

**Files:** new `tests/test_quickstart_path.py`. No source changes.

**Pattern file:** the helpers at the top of `tests/test_cli.py` (`invoke`,
`PLACEHOLDER_URL`, and the `run_stub()` usage inside `quickstart_against_stub`).

Every existing CLI test starts from `copy_quickstart`, which copies a tree into a
directory pytest already made. That is why §G1's crash shipped. This test starts where
a human starts: with nothing on disk.

Write one class that walks the README quickstart in order, inside `run_stub()`:

1. `invoke("init", ...)` into a path under `tmp_path` **that does not exist yet**.
2. Rewrite the scaffolded manifest's `PLACEHOLDER_URL` to the stub's `base_url` — the
   scaffold hardcodes `http://localhost:8000` and the stub is on a random port.
   `quickstart_against_stub` in `tests/test_cli.py` does the same string replace.
3. `invoke("freeze", <manifest>)`.
4. `invoke("run", <manifest>, "--results", …, "--report", …, "--ledger", …)` — pass all
   three paths explicitly into `tmp_path`, because their defaults are relative and would
   otherwise litter the repo root during a test run.

**Assertions** (prose):

- The `init` invocation exits 0 and its output names `audition.yaml` and all five case
  files.
- After `freeze`, an `audition.lock` exists beside the manifest and the command exits 0.
- The `run` exits 0 and its output contains `MET`.
- `results.json` and `report.html` both exist at the paths that were passed, and the
  report text contains the candidate name `stub`.

**Gate:** §G0's five commands. (This test only passes once §G1 has landed.)

## §G4 — the freeze story on the same fresh path

**Files:** `tests/test_quickstart_path.py` (a second class in the file §G3 created).
No source changes.

**Pattern file:** `lower_the_bar` in `tests/test_cli.py` for the edit, and
`TestRebarredReport` in `tests/test_report.py` for what a REBARRED report contains.

The README's `## The freeze mechanic` section makes three promises to a reader who
follows it literally. Pin all three on a scaffold made by `bakeoff init`, not on the
shipped example tree.

Walk it inside `run_stub()`: init into a fresh path, point it at the stub, freeze, then
edit the manifest's bar on disk exactly as the README shows — `min_pass_rate: 0.8`
becomes `min_pass_rate: 1.0` — and run twice.

**Assertions** (prose):

- The plain `run` after the bar edit exits `2` and its output names `--rebar`.
- `run` with `--rebar` exits 0 and writes a report.
- That report's text contains `REBARRED`.
- The report carries two different hash strings — the frozen one and the one the run
  actually used — so a reader can see the bar moved.

**Gate:** §G0's five commands.

## §G5 — `scripts/live-check.sh`: the real-endpoint proof

**Files:** new `scripts/live-check.sh`. No source changes, no CI change.

**Pattern file:** `scripts/scrub-check.sh` — copy its shape exactly: the explanatory
header comment, `set -uo pipefail`, `cd "$(dirname "$0")/.."`, and a small `report`
function that sets a `fail` flag rather than exiting mid-script.

SPEC.md names this script three times and DECISIONS.md locks it: it is the one script a
**human** runs to prove bakeoff works against a real OpenAI-compatible endpoint. CI must
never run it and `verify.sh` must never run it — it is the only thing in the repo that
touches a network.

What it does:

- Reads the endpoint from `$BAKEOFF_BASE_URL` and the model id from `$BAKEOFF_MODEL`.
- With either unset, prints a short usage block naming both variables and exits
  non-zero. That is the only way to run it without a model, and it is what your gate
  will exercise.
- Otherwise: scaffolds a throwaway audition into a temp directory with
  `uv run bakeoff init`, rewrites the candidate's `base_url` and `model` in the
  scaffolded `audition.yaml` to the two variables, then runs `uv run bakeoff freeze`
  and `uv run bakeoff run` against it.
- Exits with whatever `bakeoff run` exited with, and prints that number, so a human can
  see 0 (bar met), 1 (bar missed) or 2 (misconfigured).

**Hard constraint — this repo is public.** No real hostname and no real IP anywhere in
the file, including the usage text and comments. Examples use `localhost` or the RFC
5737 documentation range `192.0.2.10`; `scrub-check.sh` fails the gate on anything else.
Never ship a default value that points somewhere real — unset means unset.

**Gate:** §G0's five commands, plus run `bash scripts/live-check.sh` with neither
variable set and confirm it prints the usage and exits non-zero.

## §G6 — README: the real-endpoint half, and a stale gate count

**Files:** `README.md` only. Docs task.

Two edits.

**1. Add `## Auditing a real endpoint`**, immediately after `## The freeze mechanic`.
SPEC.md feature 9 asks the README quickstart for "stub audition, then a real endpoint";
only the stub half exists today. Show the two environment variables and the one command
from §G5, in the same fenced-block style the `## Quickstart` section already uses. Then
state plainly, in one or two sentences, that this project has never run that check
against a real model — the loop only ever audited the bundled stub, and any claim about
real models is a human's to make. Addresses in the prose use `localhost` or `192.0.2.x`.

**2. Fix the stale `## Development` section.** It lists five commands and closes with
"All five must be green before any change lands." There are six gates now — `readme-lint`
landed in Phase F. Add the sixth to the list, correct the closing sentence, and mention
that `bash verify.sh` runs all of them and prints a `6/6` summary.

Change nothing else in the README. The `## Status` section's two honest caveats (the
hero screenshot, and no real-endpoint claim) are still true and stay as they are.

**Gate:** `bash verify.sh` green, reporting `6/6 gates passed`.

## §G7 — teach `readme-lint` about script paths, and put it in CI

**Files:** `scripts/readme-lint.sh` and `.github/workflows/ci.yml`.

This task exists because §G5 and §G6 exposed the hole. `README.md` has named
`scripts/live-check.sh` since Phase F while the file did not exist, and `readme-lint`
passed every time — it checks `bakeoff <subcommand>` and `python -m bakeoff.<module>`,
but never a script path. §G6 adds a second script reference to the README, so the check
has to grow with it.

**1. Third check in `scripts/readme-lint.sh`**, mirroring the two `while IFS= read -r`
loops already in the file: every `scripts/<name>.sh` path the README mentions must exist
as a file in the repo. Reuse the existing `report` function and the `fail` flag. Update
the final "clean (N commands/modules checked)" line so its count includes the new
category.

**2. One step in `.github/workflows/ci.yml`**, appended after the existing `scrub-check`
step and mirroring it exactly: run `bash scripts/readme-lint.sh`. CI runs five gates
today; `verify.sh` runs six. Do **not** add `live-check.sh` to CI — it makes network
calls and is human-run by design.

**Prove the new check actually fails:** add a line to `README.md` naming a script that
does not exist, run `bash scripts/readme-lint.sh`, confirm it exits non-zero, then undo
your own edit to `README.md` before committing. A check that cannot fail is not a check.

**Gate:** `bash verify.sh` green, reporting `6/6 gates passed`.

## §G8 — close Phase G

Run `bash verify.sh` and confirm `6/6 gates passed`. Then, in three files:

**`STATUS.md`** — append a `## Phase G` section at the end, in the shape of the
`## Phase F` section above it: what shipped, then a "Still missing" sentence. Name the
`init` crash fix, the two message/doc corrections, `tests/test_quickstart_path.py`,
`scripts/live-check.sh`, the README's real-endpoint section, and the `readme-lint`
script-path check. Still missing: the README hero screenshot, and any real-endpoint run.

**`ROADMAP.md`** — flip row 7 and row 9 from PARTIAL back to `SHIPPED`, phase `G`, and
extend each note with one clause: row 7 that `bakeoff init` now works into a directory
that does not exist and the stranger's path is pinned by `tests/test_quickstart_path.py`;
row 9 that `scripts/live-check.sh` and the README's real-endpoint section shipped in G.
Then append these three lines to the reservations ledger, each naming its section:

- `live-check.sh` is written but has never been run by the loop; any claim that a real
  endpoint was audited is human-gated (§G5).
- CI runs the same six gates as `verify.sh` but never `live-check.sh`, which is the one
  thing in the repo that makes a network call (§G7).
- The README hero screenshot remains the single open item and needs a human with a
  browser (§G6).

**`TODO.md`** — tick §G8.

**Gate:** `bash verify.sh` green.
