# Phase C — the runner: ask every candidate, score it against the bar

**ROADMAP row this phase ships:** row 5 (*Runner — async httpx, retries, concurrency,
usage capture*), which reads NOT BUILT today. Row 9 (deploy-grade packaging) moves too:
its JSONL run ledger lands here.

The hard module is already committed (`feat(C0)`): `src/bakeoff/runner.py` runs a whole
audition against the seam with retries, backoff and a per-candidate concurrency cap, and
`src/bakeoff/scoring.py` opens the aggregation module. The tasks below finish the row on
top of them: the stub gains the one reply shape the runner's error path needs, scoring
gains its two functions, the runner gets its stub-backed end-to-end proof, and the run
ledger gets written.

## §C0 — house rules for every task in this phase

Read this once; §C1–§C6 assume it.

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
  `.` or `(` in it, or ruff RUF043 will fail you.
- Never add a runtime dependency; never add `# type: ignore`; never loosen a ruff or
  mypy setting. A task that genuinely cannot pass strict typing is a BLOCKED.md.
- Line length 100.

**What C0 already gives you** (grep, do not read whole):

- `src/bakeoff/runner.py`: `RetryPolicy`, `CaseOutcome`, `RunResults`, `run_case`,
  `run_pair`, `run_audition`, `run_audition_sync`. A `CaseOutcome` carries
  `candidate`, `suite`, `case_id`, `passed`, `score`, `latency_ms`, `prompt_tokens`,
  `completion_tokens`, `attempts`, `error`, plus `.total_tokens` and `.errored`.
- `src/bakeoff/scoring.py`: `percentile`, and the two empty-of-logic shapes
  `PairSummary` and `PairVerdict`. Read their docstrings — they name every field you
  must fill.
- `src/bakeoff/client.py`: `HttpClient`, `open_client`, `chat_completion`,
  `ClientError`. Nothing outside this module may import `httpx` — except tests.
- `tests/test_runner.py`: helpers `fake_client`, `completion_body`, `make_candidate`,
  `make_case`, `make_suite`, `make_audition`, `RecordingSleeper`.

**Commit** the source files you changed, by name. Never `git add .` — the repo has
untracked loop scratch (`.plan-stamps/`, `plan.log`) that must never be committed.

## §C1 — the stub can return a malformed reply

**Files:** `src/bakeoff/stub.py` (edit) and `tests/test_stub_end_to_end.py` (append a
new test class).

**Pattern file:** `error_status` in `src/bakeoff/stub.py` and `TestErrorStatus` in
`tests/test_stub_end_to_end.py`. Read those two first; this is their sibling, down to
the docstring style and the `do_POST` wiring.

The runner records a reply that is *not* a chat completion as an error outcome. The
bundled stub cannot produce one today, so that promise is only proved through a fake
transport. Give the stub a prompt prefix for it.

Add `malformed_reply(prompt: str) -> dict[str, Any] | None`: when the stripped prompt
starts with `malformed:` return a small dict that is a valid JSON object but **has no
`choices` key** (an `{"error": {...}}` shape is fine); otherwise return `None`.

Wire it into `do_POST` immediately after the existing `error_status` check: when
`malformed_reply` returns a body, send it with `self._send_json(200, body)` and
return. The point is HTTP 200 with an unusable body — that is what the runner must
survive.

**Tests** (new class `TestMalformedReply`), asserting:

1. `malformed_reply("malformed: anything")` returns a dict with no `"choices"` key;
2. an ordinary prompt returns `None`;
3. end-to-end through `run_stub()` and the `ask` helper already in that file, a
   `malformed:` prompt raises `ClientError` and the message mentions `choices`;
4. a `malformed:` prompt still returns HTTP 200, not a 4xx or 5xx — assert the
   `ClientError` message does **not** contain `HTTP 4` or `HTTP 5`.

**Gate:** the five commands in §C0.

## §C2 — summarize: outcomes to one row per suite x candidate

**Files:** `src/bakeoff/scoring.py` (edit; append below `PairVerdict`) and
`tests/test_scoring.py` (append a new test class).

**Pattern file:** `PairSummary` in the same file — its docstring names every field —
and `TestPercentile` plus the `outcome(...)` helper in `tests/test_scoring.py`. That
helper builds a `CaseOutcome` with everything defaulted, so a test names only what it
varies; use it.

Add `summarize(outcomes: Sequence[CaseOutcome]) -> tuple[PairSummary, ...]`. Group the
outcomes by their `(suite, candidate)` pair, keeping first-seen order (a plain dict
keyed by the pair does this), and build one `PairSummary` per group:

- `cases` = how many outcomes are in the group;
- `passed` = how many have `passed` true;
- `errors` = how many have `errored` true;
- `pass_rate` = `passed / cases`;
- `p95_latency_ms` = `percentile([...latency_ms...], 0.95)` — reuse the function
  above it, do not write a second percentile;
- `max_tokens_per_case` = the largest `total_tokens` in the group, or 0 if empty.

You will need to add `from .runner import CaseOutcome` to the imports.

**Tests** (new class `TestSummarize`), asserting:

1. outcomes from two candidates on one suite produce two summaries, in the order the
   candidates first appear;
2. three passes out of four outcomes give `pass_rate == 0.75` and `passed == 3`;
3. an errored outcome is counted in both `errors` and `cases`, so it lowers
   `pass_rate`;
4. `p95_latency_ms` equals `percentile` of that group's latencies;
5. `max_tokens_per_case` is the largest prompt+completion total in the group.

**Gate:** the five commands in §C0.

## §C3 — judge: hold each summary against the pre-registered bar

**Files:** `src/bakeoff/scoring.py` (edit; append below `summarize`) and
`tests/test_scoring.py` (append a new test class).

**Pattern file:** `PairVerdict` in the same file, and `Bar.for_pair` in
`src/bakeoff/manifest.py` — grep `def for_pair` and read it. `for_pair(suite,
candidate)` already merges the manifest's overrides and hands back the `Thresholds`
that apply to one pair; call it, never re-implement override merging.

Add two functions:

`judge(summaries: Sequence[PairSummary], bar: Bar) -> tuple[PairVerdict, ...]` — one
verdict per summary, in the same order. For each summary get its thresholds from
`bar.for_pair(...)` and collect a reason string for each of the three breaches:

- `pass_rate` **below** `min_pass_rate`;
- `p95_latency_ms` **above** `max_p95_latency_ms`;
- `max_tokens_per_case` **above** `max_tokens_per_case`.

Each reason names the measurement and the bar it missed, e.g.
`pass rate 0.75 is below the bar 0.90`. `met` is true exactly when there are no
reasons. Equal to the threshold clears the bar in all three cases — the bar is a
minimum/maximum, not a strict inequality.

`exit_code(verdicts: Sequence[PairVerdict]) -> int` — 0 when every verdict is met,
1 otherwise. This is the number `bakeoff run` will return, which is what makes an
audition usable as a CI regression test.

You will need `from .manifest import Bar, Thresholds` (the module already imports
`Thresholds`).

**Tests** (new class `TestJudge`), asserting:

1. a summary that clears all three thresholds is `met` with empty `reasons`;
2. a pass rate under the bar is not met and its reason mentions "pass rate";
3. a p95 latency over the bar is not met and its reason mentions latency;
4. a bar override that names one suite/candidate pair is what that pair is judged
   against — build a `Bar` with one entry in `overrides` and check the tighter
   threshold is the one applied;
5. `exit_code` is 0 when every verdict is met and 1 when any is not.

Build the `Bar` with `Bar.model_validate({"defaults": {...}, "overrides": [...]})`.

**Gate:** the five commands in §C0.

## §C4 — the runner, end to end against the bundled stub

**Files:** `tests/test_runner.py` only (append a new test class). No source changes.

**Pattern file:** `TestRunAudition` at the bottom of the same file for the async
plumbing, and `tests/test_examples.py` for how the quickstart audition is loaded
(`load_audition(AUDITION_PATH)`).

The fake-transport tests prove the retry logic. This task proves the same runner
against a real socket: the bundled stub, on a random port, no network. Add a class
`TestRunAuditionEndToEnd`.

The quickstart manifest names `http://localhost:8000`, but `run_stub()` binds a random
port, so inside the `with run_stub() as base_url:` block point the candidate at it by
assigning `audition.manifest.candidates[0].base_url = base_url` before running.
Drive the run with `asyncio.run(run_audition(audition))`.

**Tests**, asserting:

1. running the quickstart audition returns five outcomes, one per case, all with
   `candidate == "stub"` and `suite == "smoke"`;
2. every outcome passed — the quickstart is built to clear the stub — and none is
   `errored`;
3. every outcome has `attempts == 1` and `total_tokens > 0`, so usage really is
   captured through the seam;
4. a one-case suite whose prompt is `status:503: nope` (build it with the `make_case`
   and `make_suite` helpers, and point `make_candidate()`'s `base_url` at the stub)
   comes back `errored` with `attempts` equal to the policy's `max_attempts` — pass
   `RetryPolicy(max_attempts=2, backoff_base_s=0.0)` so the test is quick;
5. the same, for a `malformed: x` prompt (the §C1 prefix): `errored` is true and the
   audition still returns an outcome rather than raising.

**Gate:** the five commands in §C0.

## §C5 — the JSONL run ledger

**Files:** `src/bakeoff/ledger.py` (new) and `tests/test_ledger.py` (new).

**Pattern file:** `src/bakeoff/scoring.py` for module shape (docstring, `from
__future__ import annotations`, small pure functions) and `tests/test_scoring.py` for
test shape. `ledger.jsonl` is already in `.gitignore`; never commit one.

SPEC.md feature 9 asks for a JSONL run ledger: one JSON object per line, one line per
audition run, appended forever so a repo accumulates a history of what each model
scored. Write the file that does it. Nothing calls it yet — the CLI wires it up in a
later phase.

Add:

- `LEDGER_FILENAME = "ledger.jsonl"`.
- `run_record(results: RunResults, verdicts: Sequence[PairVerdict], *, manifest: str)
  -> dict[str, Any]` — a JSON-safe dict holding `started_at`, `finished_at`,
  `manifest`, `cases` (how many outcomes), `met_bar` (true when every verdict is met),
  and `pairs`: one entry per verdict with the summary's fields plus `met` and
  `reasons`. `dataclasses.asdict(verdict.summary)` gives you the summary fields;
  `reasons` must be a `list`, not a tuple, so it survives JSON.
- `append_run(path: str | Path, record: dict[str, Any]) -> None` — create the parent
  directory if needed, then append one line: `json.dumps(record, sort_keys=True)`
  followed by `"\n"`. Open with mode `"a"`.
- `read_ledger(path: str | Path) -> list[dict[str, Any]]` — every line decoded, in
  file order; a path that does not exist returns `[]`; blank lines are skipped.

**Tests** (`tests/test_ledger.py`, use the `tmp_path` fixture), asserting:

1. `append_run` on a fresh path writes one line and `read_ledger` returns one record
   equal to what went in;
2. appending twice gives two records, in the order they were written;
3. `read_ledger` on a path that does not exist returns an empty list;
4. `run_record` sets `met_bar` false when any verdict is not met, true when all are;
5. `json.dumps(run_record(...))` does not raise — every value is JSON-safe.

Build the `RunResults`, `PairSummary` and `PairVerdict` inputs inline in the test;
copy the `outcome(...)` helper's style from `tests/test_scoring.py`.

**Gate:** the five commands in §C0.

## §C6 — close the phase

**Files:** `STATUS.md` (append) and `ROADMAP.md` (edit rows).

Run `bash verify.sh`. All five gates must be green before you touch either doc; if one
is red, fix it or write BLOCKED.md.

Then:

- Append a `## Phase C` section to `STATUS.md`, in the shape of the `## Phase B`
  section already there: one paragraph naming what shipped (the runner, the malformed
  stub reply, `summarize`/`judge`/`exit_code`, the run ledger) and one sentence naming
  what is still missing (the freeze/lockfile and REBARRED mechanic, the report, the
  CLI, `docs/PROCESS.md`).
- In `ROADMAP.md`, set row 5 to `SHIPPED` in phase `C`. Update row 9's note to say the
  JSONL ledger shipped in C and that the README quickstart and `docs/PROCESS.md` are
  what is left. Leave every other row alone.
- Add one line to the reservations ledger at the bottom of `ROADMAP.md`: the run
  ledger is written but not yet called by anything — the CLI's `run` command wires it
  up (§C5).

**Gate:** `bash verify.sh` green.
