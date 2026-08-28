# Phase B — the audition on disk: manifest, suites, and the last grader

**ROADMAP rows this phase moves:** row 1 (audition manifest), row 2 (task suites as
files), row 3 (graders — `json-schema` is the last one missing). Rows 1 and 2 read
NOT BUILT today; row 3 reads PARTIAL.

The `feat(B0)` commits already landed the two hard modules: `src/bakeoff/manifest.py`
(pydantic models + `load_manifest`) and `src/bakeoff/suite.py` (case models, the
grader-spec union, `load_suite`), plus `src/bakeoff/errors.py`. The tasks below
finish the rows on top of them.

## §B0 — house rules for every task in this phase

Read this once; §B1–§B6 assume it.

**The gate** — all five, every task, no exceptions:

```
uv run ruff check . && uv run ruff format --check . && uv run mypy \
  && uv run pytest && bash scripts/scrub-check.sh
```

Red is not done. If `ruff format --check` complains, run `uv run ruff format .`.
`bash verify.sh` runs the same five with a summary.

**Conventions this repo already uses** — mirror them, do not invent:

- `mypy` runs `--strict` over `src/` **and** `tests/`. Every function needs
  annotations, tests included: `def test_something(self) -> None:`. A missing
  `-> None` is the most likely reason your gate goes red.
- Every module starts with a docstring, then `from __future__ import annotations`.
- Never add a runtime dependency; never add `# type: ignore`; never loosen a ruff or
  mypy setting. A task that genuinely cannot pass strict typing is a BLOCKED.md.
- Line length 100.

**What B0 already gives you** (grep, do not read whole):

- `src/bakeoff/manifest.py`: `Manifest`, `Candidate`, `Profile`, `SuiteRef`, `Bar`,
  `Thresholds`, `BarOverride`, `ManifestError`, `load_manifest`, `parse_manifest`,
  `suite_dir`.
- `src/bakeoff/suite.py`: `Case`, `Suite`, `SuiteError`, `load_suite`, `parse_case`,
  and five grader-spec classes — `ExactSpec`, `ContainsSpec`, `RegexSpec`,
  `NumericToleranceSpec`, `JsonSchemaSpec` — unioned as `GraderSpec`.
- Import direction is fixed: `errors` <- `graders`/`suite` <- `manifest`.
  `suite.py` must never import `manifest.py`; that would be a cycle.

**Commit** the source files you changed, by name. Never `git add .` — the repo has
untracked loop scratch (`.plan-stamps/`, `plan.log`) that must never be committed.

## §B1 — grade_json_schema, the last grader

**Files:** `src/bakeoff/graders.py` (edit; append below `grade_numeric_tolerance`)
and `tests/test_graders.py` (append a new test class).

**Pattern file:** `grade_numeric_tolerance` in the same file, and
`TestGradeNumericTolerance` in the same test file. Read those two first; your
function and tests are their siblings, down to the docstring style and the `_binary`
helper.

Add `grade_json_schema(completion, schema, ...)`: it parses the completion as JSON
and validates it against a JSON Schema. `schema` is a `dict[str, Any]`.

Rules:

- Parse the stripped completion with `json.loads`. A completion that is not JSON is
  a **failing grade**, not an exception — return a failed `GradeResult` whose detail
  says the completion was not JSON.
- Valid JSON that does not satisfy the schema is a failing grade; put the validator's
  own message (`exc.message`) in the detail.
- A schema that is itself malformed is an **author error**: catch
  `jsonschema.SchemaError` and raise `GraderConfigError`, exactly the way
  `grade_regex` does for a pattern that will not compile.
- `import json` goes at the top of the module with the other imports; so does
  `import jsonschema`. Both are already available — `jsonschema` is a pre-registered
  dependency and its type stubs are installed.

`jsonschema.validate(instance, schema)` raises `jsonschema.ValidationError` when the
instance is wrong and `jsonschema.SchemaError` when the schema is wrong. Both carry a
`.message` attribute.

**Tests** (new class `TestGradeJsonSchema`), asserting:

1. an object matching a small `{"type": "object", "required": [...]}` schema passes
   with score 1.0;
2. valid JSON that is missing a required property fails with score 0.0;
3. the failure detail mentions the missing property name;
4. a completion that is not JSON at all fails rather than raising;
5. a malformed schema (for example `{"type": "not-a-type"}`) raises
   `GraderConfigError` — use `pytest.raises`.

**Gate:** the five commands in §B0.

## §B2 — run_grader: turn a case's grader spec into a grade

**Files:** `src/bakeoff/suite.py` (edit; append at the end of the module) and
`tests/test_suite.py` (append a new test class).

**Pattern file:** the five spec classes at the top of `src/bakeoff/suite.py` — each
one carries exactly the arguments of its grader in `src/bakeoff/graders.py`. Grep
both files for `class ExactSpec` and `def grade_exact` and read those.

Add `run_grader(spec: GraderSpec, completion: str) -> GradeResult`: the one place
that maps a validated spec onto the grader function that implements it. Nothing else
in the package is allowed to know that mapping.

Write it as a chain of `isinstance` checks, one per spec class, each returning the
matching grader call with the spec's fields passed through as keyword arguments where
the grader declares them keyword-only:

- `ExactSpec` -> `grade_exact`, passing `strip`.
- `ContainsSpec` -> `grade_contains`, passing `case_sensitive`.
- `RegexSpec` -> `grade_regex`, passing `fullmatch`.
- `NumericToleranceSpec` -> `grade_numeric_tolerance`, passing `tolerance`.
- `JsonSchemaSpec` -> `grade_json_schema`, passing `spec.json_schema` as the schema
  (the YAML key is `schema`; the Python attribute is `json_schema`).

After the five branches, end the function by raising `GraderConfigError` naming the
spec — unreachable today, but it is what makes a sixth spec class added without a
branch fail loudly instead of silently.

Import the grader functions and `GradeResult` from `.graders` at the top of the
module; `GraderConfigError` too.

**Tests** (new class `TestRunGrader`), asserting:

1. an `ExactSpec` grade of a matching completion passes;
2. a `ContainsSpec` with `case_sensitive=False` passes on a different-cased
   completion;
3. a `RegexSpec` with `fullmatch=True` fails on a completion the pattern only
   partially matches;
4. a `NumericToleranceSpec` passes a value inside its tolerance and fails one
   outside it;
5. a `JsonSchemaSpec` passes valid JSON and fails JSON that breaks the schema.

Build the specs directly (`ExactSpec(kind="exact", expected="4")`) or via
`parse_case`, whichever reads better.

**Gate:** the five commands in §B0.

## §B3 — load_audition: one call that loads a manifest and its suites

**Files:** `src/bakeoff/manifest.py` (edit; append at the end) and
`tests/test_manifest.py` (append a new test class).

**Pattern file:** `load_manifest` at the bottom of `src/bakeoff/manifest.py`, and the
`Suite` dataclass in `src/bakeoff/suite.py`.

A manifest names its suites by relative path; nothing yet reads them. Add the join.

1. Add a frozen dataclass `Audition` with two fields: `manifest: Manifest` and
   `suites: tuple[Suite, ...]`, the suites in manifest order. Give it a
   `suite(name: str) -> Suite` lookup that raises `KeyError` when there is no such
   suite, mirroring `Manifest.candidate` a few lines above.
2. Add `load_audition(path: str | Path) -> Audition`: call `load_manifest(path)`,
   then for each `SuiteRef` resolve its directory with the existing `suite_dir(path,
   ref)` and load it with `load_suite(directory, name=ref.name)`.
3. When `load_suite` raises `SuiteError`, catch it and re-raise a `ManifestError`
   that names the manifest path, the suite name, and the resolved directory, then the
   original message. A missing suite directory is a manifest problem — the manifest
   is what pointed at it.

Add `from .suite import Suite, SuiteError, load_suite` to the imports at the top of
`manifest.py`, and `from dataclasses import dataclass`. That import direction is the
allowed one; `suite.py` never imports `manifest.py`.

**Tests** (new class `TestLoadAudition` in `tests/test_manifest.py`), asserting:

1. a manifest whose one suite directory exists loads, and the returned `Audition`
   carries that suite's cases;
2. the suite is named for the `SuiteRef`, not the directory, when the two differ;
3. `Audition.suite("smoke")` returns it and an unknown name raises `KeyError`;
4. a manifest pointing at a directory that does not exist raises `ManifestError`, and
   the message contains the suite name.

Use the `write_manifest` helper already at the top of `tests/test_manifest.py` and
the case YAML from `tests/test_suite.py` (copy a small case string in; do not import
across test modules).

**Gate:** the five commands in §B0.

## §B4 — examples/: the audition a stranger reads first

**Files (all new):** `examples/quickstart/audition.yaml`,
`examples/quickstart/suites/smoke/` with five case files, and
`tests/test_examples.py`.

**Pattern file:** the manifest example in the module docstring at the top of
`src/bakeoff/manifest.py`, and the case-file example in the docstring at the top of
`src/bakeoff/suite.py`. Those two docstrings are the schema; copy their shape.

SPEC.md's shape section reserves `examples/` for the quickstart manifest and suites.
Write one audition that runs against the bundled stub.

`audition.yaml`: `version: 1`; one candidate named `stub` with
`base_url: http://localhost:8000`, `model: stub-model`, and a profile setting a short
system prompt, `temperature: 0.0`, `max_tokens: 64`; one suite named `smoke` at path
`suites/smoke`; a bar with defaults (`min_pass_rate: 0.8`,
`max_p95_latency_ms: 2000`, `max_tokens_per_case: 200`) and one override tightening
`min_pass_rate` to 1.0 for suite `smoke` and candidate `stub`.

Five case files under `suites/smoke/`, numbered so `ls` shows the order
(`01-...yaml` … `05-...yaml`), one per grader kind: `exact`, `contains`, `regex`,
`numeric_tolerance`, `json_schema`. Every prompt must be one the bundled stub answers
correctly, so the whole suite passes against the stub. The stub's rules are in
`canned_reply` in `src/bakeoff/stub.py`: a prompt starting `echo: ` comes back as
whatever follows it, and one starting `json: ` likewise. So `"echo: 4"` graded
`exact` against `"4"` passes. Give each case a `reference` answer where one reads
naturally.

Addresses in the repo may only be `localhost`, `127.0.0.1`, or `192.0.2.x` —
`scrub-check.sh` fails the gate on anything else.

**Tests** (`tests/test_examples.py`, a new file with one class `TestQuickstart`).
Resolve the examples directory from `Path(__file__)` the way
`tests/test_toolchain.py` resolves `PYPROJECT`. Assert:

1. `load_audition` on the example manifest returns an audition with one candidate and
   one suite;
2. the smoke suite has five cases and their grader `kind` values are the five
   distinct grader kinds;
3. for every case, `run_grader(case.grader, canned_reply(case.prompt))` passes — the
   example suite really does pass against the bundled stub;
4. the candidate's `base_url` is a `localhost` address.

**Gate:** the five commands in §B0.

## §B5 — the error paths are the product: validation tests

**Files:** `tests/test_manifest.py` and `tests/test_suite.py` (append one class to
each). No source changes.

**Pattern file:** `TestGradeRegex` in `tests/test_graders.py` for the
`pytest.raises` style, and `TestLoadManifest` / `TestLoadSuite` for how these two
files build fixtures.

SPEC.md feature 1 promises validation errors "that name the field and the fix". That
promise is only real if it is asserted. Both loaders wrap pydantic and raise
`ManifestError` / `SuiteError` whose message carries one
`  <dotted.field.path>: <what is wrong>` line per problem.

New class `TestManifestErrors` in `tests/test_manifest.py`, asserting that
`parse_manifest` (or `load_manifest`) raises `ManifestError` and that the message
mentions the named text:

1. an unknown key on a candidate — message contains `candidates.0` and the bad key;
2. `profile.temperature: 9` — message contains `temperature`;
3. a `base_url` with no scheme (`localhost:8000`) — message contains `base_url` and
   `http`;
4. two candidates sharing a name — message contains `duplicate`;
5. a `bar.overrides` entry naming a suite that is not declared — message contains the
   unknown suite name;
6. a manifest with no `bar` key at all — message contains `bar`.

New class `TestSuiteErrors` in `tests/test_suite.py`, asserting:

1. `load_suite` on a directory that does not exist raises `SuiteError`;
2. `load_suite` on an existing but empty directory raises `SuiteError`;
3. a case file with an empty `prompt` raises `SuiteError` naming `prompt`;
4. a case whose `grader.kind` is not one of the five raises `SuiteError`, and the
   message lists the valid kinds;
5. two case files that both set the same explicit `id` raise `SuiteError` mentioning
   `duplicate`.

Use `str(excinfo.value)` from `pytest.raises` to read the message. Do not assert on
exact punctuation — assert that the field name appears.

**Gate:** the five commands in §B0.

## §B6 — close the phase

**Files:** `STATUS.md` (append) and `ROADMAP.md` (edit rows). No source changes.

**Pattern file:** the `## Phase A` section already in `STATUS.md`, and the table in
`ROADMAP.md`.

First run `bash verify.sh` and confirm it exits 0. If it does not, fix what it names
before touching either document.

**STATUS.md** — append a `## Phase B` section, about eight lines: what Phase B
shipped (the audition manifest with its bar model, task suites as files, the fifth
grader and the `run_grader` dispatch, `examples/quickstart`, the validation-error
tests) and what is still missing (the freeze/lockfile and REBARRED mechanic, the
runner, the report, the CLI, `docs/PROCESS.md`). Do not rewrite anything already in
the file.

**ROADMAP.md** — edit exactly these rows:

- row 1 (audition manifest): status `SHIPPED`, phase `B`.
- row 2 (task suites as files): status `SHIPPED`, phase `B`.
- row 3 (pure graders): status `SHIPPED`, phase `B`, note `all five shipped;
  run_grader dispatches a case spec to its grader`.
- row 4 (bar + freeze): leave status `NOT BUILT`, phase `B`, note `bar model and
  per-pair thresholds shipped in B; freeze, lockfile and REBARRED pending`.

Then append one line to the **Reservations ledger** at the bottom of ROADMAP.md:
type-stub dev dependencies (`types-PyYAML`, `types-jsonschema`) were added in Phase B
because neither library ships `py.typed` and mypy --strict is never weakened; the
runtime dependency surface is unchanged (§B0).

**Gate:** `bash verify.sh` green, which is the five commands in §B0.
