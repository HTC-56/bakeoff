# Phase A — prove the stack, then finish the graders and the stub

**ROADMAP rows this phase moves:** row 3 (pure graders), row 8 (bundled stub server),
row 9 (deploy-grade packaging). None of them were SHIPPED before this phase.

The Phase A foundation is already committed (the four `feat(A0)` commits): the uv /
ruff / mypy --strict / pytest toolchain, `src/bakeoff/graders.py` with the first
grader, the `src/bakeoff/client.py` HTTP seam, the bundled stub in
`src/bakeoff/stub.py`, `scripts/scrub-check.sh`, and CI. The tasks below finish those
rows.

## §A0 — house rules for every task in this phase

Read this once; it is assumed by §A1–§A6.

**The gate** — all five, every task, no exceptions:

```
uv run ruff check . && uv run ruff format --check . && uv run mypy \
  && uv run pytest && bash scripts/scrub-check.sh
```

Red is not done. If `ruff format --check` complains, run `uv run ruff format .`.

**Python conventions this repo already uses** — mirror them, do not invent:

- `mypy` runs `--strict` over `src/` **and** `tests/`. Every function needs
  annotations, and that includes tests: a test method is
  `def test_something(self) -> None:`. A missing `-> None` is the single most likely
  reason your gate goes red.
- Every module starts with a docstring, then `from __future__ import annotations`.
- Never add a dependency. The five allowed are click, httpx, jsonschema, pydantic,
  PyYAML — all already installed.
- Never add `# type: ignore` and never loosen a ruff or mypy setting to pass. If a
  task genuinely cannot pass strict typing, that is a BLOCKED.md, not a config edit.
- Line length is 100.

**Commit** the source files you changed, by name. Never `git add .` — the repo has
untracked loop scratch (`.plan-stamps/`, `plan.log`) that must never be committed.

## §A1 — grade_contains

**File:** `src/bakeoff/graders.py` (edit; append below `grade_exact`) and
`tests/test_graders.py` (edit; append a new test class).

**Pattern file:** `grade_exact` in the same file, and `TestGradeExact` in the same
test file. Read those two first — your function and your tests should look like their
siblings, including the docstring style and the use of the `_binary` helper.

Add `grade_contains`: passes when a required substring appears anywhere in the
completion. It takes the completion, the substring to look for, and a keyword-only
`case_sensitive: bool = True`. When `case_sensitive` is False, compare with both
sides lower-cased. Return a `GradeResult` via `_binary`, exactly as `grade_exact`
does; the failure `detail` should name the substring that was missing.

**Tests** (new class `TestGradeContains` in `tests/test_graders.py`), asserting:

1. a substring in the middle of a longer completion passes with score 1.0;
2. a substring that is absent fails with score 0.0;
3. a case difference fails when `case_sensitive` is True (the default);
4. that same case difference passes when `case_sensitive=False`;
5. the failure `detail` mentions the missing substring.

**Gate:** the five commands in §A0.

## §A2 — grade_regex

**File:** `src/bakeoff/graders.py` (edit; append below your `grade_contains`) and
`tests/test_graders.py` (append a new test class).

**Pattern file:** `grade_contains` from §A1 — same shape, same `_binary` helper.

Add `grade_regex`: passes when a regular expression matches the completion. It takes
the completion, the pattern string, and a keyword-only `fullmatch: bool = False`.
With `fullmatch` False, a match anywhere in the completion passes (`re.search`); with
it True, the pattern must match the whole completion (`re.fullmatch`).

One extra rule, and it is the point of this task: a pattern that does not compile is
an **author error, not a failing case**. Catch `re.error` and raise
`GraderConfigError` (already defined at the top of the module) with a message naming
the bad pattern. Never let a broken pattern quietly score zero.

`import re` goes at the top of the module with the other imports.

**Tests** (new class `TestGradeRegex`), asserting:

1. a pattern matching part of the completion passes;
2. a pattern matching nothing fails with score 0.0;
3. a partial-only pattern fails when `fullmatch=True` but passes by default;
4. an uncompilable pattern (for example `"("`) raises `GraderConfigError` — use
   `pytest.raises`;
5. the raised message contains the offending pattern.

**Gate:** the five commands in §A0.

## §A3 — grade_numeric_tolerance

**File:** `src/bakeoff/graders.py` (edit; append below your `grade_regex`) and
`tests/test_graders.py` (append a new test class).

**Pattern file:** `grade_regex` from §A2.

Add `grade_numeric_tolerance`: passes when the completion, read as a number, is
within a tolerance of an expected value. It takes the completion, `expected: float`,
and a keyword-only `tolerance: float = 0.0`.

Rules:

- Strip the completion and parse it with `float()`. A completion that is not a number
  on its own (`"about four"`) is a **failing grade**, not an exception — return a
  failed `GradeResult` whose detail says the completion was not numeric.
- Pass when `abs(parsed - expected) <= tolerance`.
- A negative `tolerance` is an author error: raise `GraderConfigError`, the same way
  §A2 does for a bad pattern.
- The failure detail should show the parsed value, the expected value, and the
  tolerance.

**Tests** (new class `TestGradeNumericTolerance`), asserting:

1. an exact numeric match passes with the default tolerance of 0.0;
2. a value inside the tolerance passes (e.g. 3.14 against 3.1 with tolerance 0.05);
3. a value outside the tolerance fails with score 0.0;
4. a value exactly at the tolerance edge passes (the comparison is `<=`);
5. a non-numeric completion fails rather than raising;
6. a negative tolerance raises `GraderConfigError`.

**Gate:** the five commands in §A0.

## §A4 — the stub can be told to return an HTTP error

SPEC.md feature 5 requires that timeouts, refusals, and malformed replies are
recorded outcomes rather than crashes. Before the runner can record them, the stub has
to be able to produce them on demand. This task adds that switch.

**File:** `src/bakeoff/stub.py` (edit) and `tests/test_stub_end_to_end.py` (append a
new test class).

**Pattern file:** `canned_reply` in `src/bakeoff/stub.py` — a small pure function that
reads a prompt prefix — and `TestCannedReply` in the test file.

Add a new pure function `error_status(prompt: str) -> int | None` next to
`canned_reply`. It returns the status code when the stripped prompt starts with
`status:` followed by a three-digit number and a colon (`status:503: anything`), and
`None` otherwise. A malformed prefix (no digits, not three digits, no closing colon)
returns `None` — the stub then treats the prompt as an ordinary one.

Then wire it in `StubHandler.do_POST`. The anchor is the line

```
        if self.path.rstrip("/") != "/v1/chat/completions":
```

After the existing path check and the JSON decoding — that is, immediately before the
final `self._send_json(200, build_response(decoded))` line — call `error_status` on
the last user prompt (`last_user_prompt(decoded)`) and, when it returns a code, send
that status with a body shaped like the 404 branch above it (`{"error": {"message":
...}}`) and return instead.

Do **not** change `canned_reply`, and do not change `build_response`.

**Tests** (new class `TestErrorStatus` in `tests/test_stub_end_to_end.py`), asserting:

1. `error_status("status:503: overloaded")` returns 503;
2. an ordinary prompt returns `None`;
3. a malformed prefix such as `"status:abc: x"` returns `None`;
4. end-to-end: inside `with run_stub() as base_url`, calling the module-level `ask`
   helper with a `status:500:` prompt raises `ClientError`, and the message contains
   `500`. `ask` and `ClientError` are already imported at the top of that file.

**Gate:** the five commands in §A0.

## §A5 — README for the repo as it stands

**File:** `README.md` (create) and `pyproject.toml` (one-line edit).

**Pattern file:** `SPEC.md` for the wording of what bakeoff is — reuse its first
paragraph's framing in your own two sentences. Do not copy SPEC.md wholesale.

Write a short README, roughly 60 lines, with these sections and nothing more:

- **bakeoff** — two or three sentences: model selection by pre-registered audition;
  the bar is frozen before any model runs, and a bar edited afterwards is branded on
  the report rather than hidden.
- **Status** — plainly: early, built phase by phase by an autonomous coding loop; the
  CLI and the report are not built yet. Do not describe unbuilt features as working.
- **Requirements** — Python 3.12+ and uv.
- **Development** — `uv sync`, then the five gate commands from §A0, each on its own
  line in one fenced block, with a sentence saying all five must be green.
- **Running the bundled stub** — `uv run python -m bakeoff.stub --port 8000`, and one
  sentence that the test suite starts its own stub on a random port, so the whole
  suite runs with no model and no network.

Then add `readme = "README.md"` to `pyproject.toml`, in the `[project]` table
directly under the `description = ` line.

Addresses in documentation may only be `localhost`, `127.0.0.1`, or `192.0.2.x` —
`scrub-check.sh` fails the gate on anything else. No badges (CI is not public yet), no
screenshots, no quickstart section — the quickstart lands with the CLI in a later
phase.

**Gate:** the five commands in §A0.

## §A6 — verify.sh, then close the phase

**Files:** `verify.sh` (create), `STATUS.md` (append), `ROADMAP.md` (edit rows).

**Pattern file:** `scripts/scrub-check.sh` — mirror its header comment style, its
`set -uo pipefail`, and its `cd "$(dirname "$0")"` line so the script works from any
directory. `verify.sh` lives at the repo root, so its `cd` needs no `/..`.

`verify.sh` runs all five gates from §A0 in order, printing a short banner before
each. It must run every gate even when an earlier one fails, collect the failures,
print a final summary line, and exit 1 if any gate failed and 0 only when all five
passed. Make it executable (`chmod +x verify.sh`). Do not add the README-quickstart
lint that SPEC.md mentions — there is no quickstart yet; it lands with the CLI.

Then run `bash verify.sh` and confirm it exits 0.

**STATUS.md** — append a `## Phase A` section, about eight lines: what Phase A
shipped (toolchain, four graders, the HTTP seam, the stub with its error switch,
scrub-check, CI, README, verify.sh), and what is explicitly still missing (the
manifest, the bar and freeze, the runner, the report, the CLI). Do not rewrite
anything already in the file.

**ROADMAP.md** — edit exactly these rows in the table:

- row 3 (graders): status `PARTIAL`, phase `A`, note `exact, contains, regex,
  numeric-tolerance shipped; json-schema pending`.
- row 5 (runner): leave status `NOT BUILT`, phase `A`, note `client seam shipped in
  A; runner itself pending`.
- row 8 (stub server): status `SHIPPED`, phase `A`.
- row 9 (packaging): status `PARTIAL`, phase `A`, note `pyproject, CI, scrub-check,
  verify.sh, README shipped; ledger and quickstart pending`.

Then add two lines to the **Reservations ledger** at the bottom of ROADMAP.md: the
README-quickstart lint is deferred out of `verify.sh` until the CLI exists (§A6), and
the json-schema grader is deferred out of Phase A (§A3).

**Gate:** `bash verify.sh` green, which is the five commands in §A0.
