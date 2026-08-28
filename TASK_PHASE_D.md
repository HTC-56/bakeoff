# Phase D — the freeze: a bar is pre-registered, or it is not a bar

**ROADMAP row this phase ships:** row 4 (*Pre-registered bar + freeze/REBARRED
mechanic*), which reads NOT BUILT today. Row 9 (deploy-grade packaging) gains one line:
the run ledger starts recording the bar hash a run ran under.

The hard module is already committed (`feat(D0)`): `src/bakeoff/freeze.py` hashes a bar
into a lockfile and reads it back. The tasks below finish the row on top of it — the two
decision functions (*is this bar still the frozen one?* and *may this run proceed?*), the
quickstart's own committed lockfile, the hash in the ledger, and an end-to-end proof that
editing the bar after the freeze is caught rather than hidden.

## §D0 — house rules for every task in this phase

Read this once; §D1–§D6 assume it.

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

**What D0 already gives you** (grep `src/bakeoff/freeze.py`, do not read it whole):

- `canonical_bar(bar)` and `bar_hash(bar)` — a bar's identity, `sha256:` + 64 hex.
- `Lockfile` — a pydantic model with `version`, `bar_hash`, `frozen_at`, `manifest`.
- `lockfile_path(manifest_path)`, `freeze_bar(manifest, *, manifest_path, now=None)`,
  `write_lockfile(path, lock)`, `read_lockfile(path)`, `find_lockfile(manifest_path)`
  (returns `None` when no lockfile sits beside the manifest).
- `FreezeStatus` — a `StrEnum` with exactly `FROZEN`, `REBARRED`, `UNFROZEN`.
- `FreezeCheck` — a frozen dataclass holding `status`, `current_hash`,
  `frozen_hash` (`None` when unfrozen). Read its docstring; it names every field.
- `FreezeError` — the module's error type, a `ConfigError`.
- `tests/test_freeze.py`: helpers `make_bar(...)`, `make_manifest(...)`,
  `make_lockfile(...)` and the constant `FROZEN_AT`. Each defaults everything, so a
  test names only what it varies. Use them.

**Commit** the source files you changed, by name. Never `git add .` — the repo has
untracked loop scratch (`.plan-stamps/`, `plan.log`) that must never be committed.

## §D1 — check_freeze: has the bar moved since it was pre-registered?

**Files:** `src/bakeoff/freeze.py` (edit; append below `find_lockfile`) and
`tests/test_freeze.py` (append a new class at the end).

**Pattern file:** `judge` in `src/bakeoff/scoring.py` — a small pure function that
holds a measurement against a recorded expectation and returns a frozen dataclass.
This is its sibling.

Add `check_freeze(bar: Bar, lock: Lockfile | None) -> FreezeCheck`. Hash the bar you
were given, then compare:

- no lockfile → status `UNFROZEN`, `frozen_hash` `None`;
- the lockfile's `bar_hash` equals the bar's hash → status `FROZEN`;
- anything else → status `REBARRED`.

`current_hash` is always the hash of the bar passed in, in all three cases — the
report prints it even when there is nothing to compare against. `frozen_hash` is the
lockfile's recorded hash whenever there is a lockfile, including when they agree.

`Bar` is already imported at the top of the module; nothing new is needed.

**Tests** (new class `TestCheckFreeze`), asserting:

1. with `lock=None` the status is `FreezeStatus.UNFROZEN` and `frozen_hash` is `None`;
2. an unfrozen check still reports `current_hash == bar_hash(bar)` — never `None`;
3. a lockfile made by `freeze_bar` from the same manifest gives `FROZEN`, and
   `current_hash == frozen_hash`;
4. hashing one bar but checking a *different* bar (say `make_bar(min_pass_rate=0.5)`)
   gives `REBARRED`, and the two hashes differ;
5. a `REBARRED` check keeps the lockfile's hash in `frozen_hash`.

**Gate:** the five commands in §D0.

## §D2 — require_freeze: the gate a run has to pass

**Files:** `src/bakeoff/freeze.py` (edit; append below `check_freeze`) and
`tests/test_freeze.py` (append a new class at the end).

**Pattern file:** `exit_code` in `src/bakeoff/scoring.py` for the shape (a tiny pure
decision function), and `read_lockfile` in `freeze.py` for the error-message style —
every `FreezeError` says what is wrong *and* what to type next.

Add `require_freeze(check: FreezeCheck, *, rebar: bool) -> None`. It returns `None`
when the run may proceed and raises `FreezeError` when it may not:

- `FROZEN` → allowed, whatever `rebar` says (`--rebar` is permission, not a mode);
- `UNFROZEN` → raise; the message tells the caller to run `bakeoff freeze` first;
- `REBARRED` and `rebar` is false → raise; the message must print **both** hashes
  (frozen and current) and say the run needs `--rebar`;
- `REBARRED` and `rebar` is true → allowed. The run is legal and the report brands
  it; this function's job is only to stop the *silent* version.

**Tests** (new class `TestRequireFreeze`), asserting:

1. a `FROZEN` check with `rebar=False` returns `None`;
2. a `FROZEN` check with `rebar=True` also returns `None`;
3. an `UNFROZEN` check raises `FreezeError` mentioning `bakeoff freeze`;
4. a `REBARRED` check with `rebar=False` raises `FreezeError` whose message contains
   both the frozen hash and the current hash — assert with `in str(excinfo.value)`,
   not with `match=`, because a digest in a regex is noise;
5. the same `REBARRED` check with `rebar=True` returns `None`.

Build the `FreezeCheck` values directly in the test — it is a plain dataclass.

**Gate:** the five commands in §D0.

## §D3 — the quickstart ships a frozen bar

**Files:** `examples/quickstart/audition.lock` (new, generated — see below) and
`tests/test_examples.py` (append a new class at the end).

**Pattern file:** `TestQuickstart` in `tests/test_examples.py` — same
`EXAMPLES_DIR` / `AUDITION_PATH` constants, same one-assertion-per-test shape.

The example audition declares a bar but has never pre-registered it. Freeze it, and
commit the lockfile — that is what a real user's repo looks like. Generate the file
by running the module rather than writing YAML by hand:

```
uv run python -c "from pathlib import Path; from bakeoff.manifest import load_manifest; from bakeoff.freeze import freeze_bar, lockfile_path, write_lockfile; p = Path('examples/quickstart/audition.yaml'); write_lockfile(lockfile_path(p), freeze_bar(load_manifest(p), manifest_path=p))"
```

Then `cat` it: it should carry a `# bakeoff lockfile` header, a `sha256:` hash, a
`frozen_at` timestamp, and `manifest: audition.yaml`.

**Tests** (new class `TestQuickstartFreeze`), asserting:

1. `find_lockfile(AUDITION_PATH)` is not `None` — the example ships pre-registered;
2. `check_freeze(load_manifest(AUDITION_PATH).bar, find_lockfile(AUDITION_PATH))` has
   status `FreezeStatus.FROZEN`;
3. the lockfile's `manifest` field is `"audition.yaml"` — a name, never a path;
4. the lockfile's `bar_hash` starts with `sha256:`.

Test 2 is the point of the task: from now on, anyone who edits the example bar
without re-freezing turns the suite red. If it fails, that is the mechanic working —
do not weaken the test.

**Gate:** the five commands in §D0. Commit the generated `.lock` file too.

## §D4 — the ledger records the bar a run ran under

**Files:** `src/bakeoff/ledger.py` (edit `run_record`) and `tests/test_ledger.py`
(append a new class at the end).

**Pattern file:** `run_record` itself — you are adding one key to the dict it already
builds — and `TestRunRecord` in `tests/test_ledger.py` for the test shape.

SPEC.md feature 4 says `bakeoff run` records the bar hash it ran under. Give
`run_record` a new keyword-only parameter `freeze: FreezeCheck | None = None`
(defaulting to `None` so existing callers keep working) and add one key, `"freeze"`,
to the returned dict:

- when `freeze` is `None` → the value is `None` (this run was never checked);
- otherwise → a small dict with `"status"` (use `freeze.status.value`, a plain
  string), `"bar_hash"` (the check's `current_hash`) and `"frozen_hash"`.

Everything already in the record stays exactly as it is. Import `FreezeCheck` from
`.freeze`. Also add one sentence to the module docstring saying the record carries
the freeze state.

**Tests** (new class `TestRunRecordFreeze`), asserting:

1. with no `freeze` argument, `record["freeze"]` is `None` and the other keys
   (`started_at`, `manifest`, `cases`, `met_bar`, `pairs`) are all still present;
2. given a `FROZEN` check, `record["freeze"]["status"] == "frozen"` and
   `record["freeze"]["bar_hash"]` is the check's `current_hash`;
3. given a `REBARRED` check, the status is `"rebarred"` and the two hashes differ;
4. the whole record still survives `json.dumps` — the enum must not leak into it.

**Gate:** the five commands in §D0.

## §D5 — the REBARRED proof, end to end on disk

**Files:** `tests/test_freeze.py` only (append a new class at the end). No source
changes.

**Pattern file:** `TestRunAuditionEndToEnd` in `tests/test_runner.py` for the shape of
an end-to-end class, and `TestWriteAndReadLockfile` in this same file for `tmp_path`
use.

Everything so far is proved on hand-built objects. This class proves the mechanic the
way a user meets it: a manifest on disk, frozen, then edited.

In one `tmp_path`, copy the example manifest's *text* —
`Path("examples/quickstart/audition.yaml").read_text()` written to
`tmp_path / "audition.yaml"`. Use `load_manifest`, **not** `load_audition`: the suite
directories are not copied and do not need to be, because the freeze is about the bar
alone. Freeze it with `freeze_bar` + `write_lockfile(lockfile_path(...), ...)`, then
lower the bar by rewriting the file text with `min_pass_rate: 0.8` replaced by
`min_pass_rate: 0.5` (that string appears exactly once), and re-load.

**Tests** (new class `TestRebarredEndToEnd`), asserting:

1. straight after freezing, `check_freeze(manifest.bar, find_lockfile(path))` is
   `FROZEN` and `require_freeze(..., rebar=False)` returns `None`;
2. after the edit, the same check is `REBARRED`;
3. the rebarred check's `frozen_hash` is the hash still recorded in the lockfile on
   disk, and its `current_hash` is the hash of the lowered bar — the report needs
   both, so assert they differ and that neither is `None`;
4. `require_freeze(rebarred_check, rebar=False)` raises `FreezeError`, and the same
   check with `rebar=True` returns `None`;
5. re-freezing the edited manifest and writing the lockfile again returns the pair to
   `FROZEN` — a deliberate re-registration is always allowed.

**Gate:** the five commands in §D0.

## §D6 — close the phase

**Files:** `STATUS.md` (append) and `ROADMAP.md` (edit rows).

Run `bash verify.sh`. All five gates must be green before you touch either doc; if one
is red, fix it first — that is the task.

Then append a `## Phase D` section to `STATUS.md`, mirroring the `## Phase C` section
directly above it: two or three sentences naming what shipped (the freeze module, the
freeze check and its run gate, the quickstart lockfile, the bar hash in the ledger,
the REBARRED end-to-end proof) and one sentence naming what is still missing (the
report, the CLI, `docs/PROCESS.md`).

Then in `ROADMAP.md`:

- row 4 (*Pre-registered bar + freeze/REBARRED mechanic*): status `SHIPPED`, phase
  `D`, note that the lockfile, the freeze check and the `--rebar` gate are built and
  that the report's REBARRED branding lands with the report;
- row 9 (*Deploy-grade packaging*): keep it `PARTIAL`, and add to its note that the
  ledger now records the bar hash per run;
- append to the reservations ledger at the bottom: the `--rebar` **flag** itself is
  the CLI's, not this phase's — `require_freeze` is the gate the CLI will call (§D2);
  and the report's REBARRED branding is the report phase's work (§D5).

Do not edit any other row and do not rewrite the file.

**Gate:** `bash verify.sh` green, then commit both docs.
