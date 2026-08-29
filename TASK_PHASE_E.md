# Phase E — the report: one self-contained HTML file, and the JSON behind it

**ROADMAP row this phase ships:** row 6 (*Report — self-contained HTML + results.json
+ exit code*), which reads NOT BUILT today. No other row is the subject of this phase.

The hard module is already committed (`feat(E0)`): `src/bakeoff/report.py` builds the
results document, writes and reads `results.json`, and renders a whole HTML page with
the header, the freeze banner and the scoreboard. The tasks below finish the row on
top of it — the per-case drill-down with the actual completions, the latency-and-token
spend table, the REBARRED branding proved from a bar edited on disk, the
self-containment promise, and the whole pipeline run end to end against the bundled
stub.

## §E0 — house rules for every task in this phase

Read this once; §E1–§E6 assume it.

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

**The one rule the report itself must never break:** the page is self-contained.
No `<script>`, no `<link>`, no `@import`, no `url(...)`, no CDN, no web font — a
report mailed as a single file must render on a machine with no network. Drill-down
is `<details>`/`<summary>`, never JavaScript. Do not add a second `<style>` block:
every class you need already exists (see below).

**What E0 already gives you** (grep `src/bakeoff/report.py`, do not read it whole):

- `results_document(results, verdicts, *, manifest, freeze=None, generated_at=None)`
  → the JSON-safe dict everything else renders from. Keys: `version`,
  `generated_at`, `manifest`, `started_at`, `finished_at`, `freeze`, `met_bar`,
  `exit_code`, `pairs`, `cases`.
- Each entry of `document["pairs"]`: `suite`, `candidate`, `cases`, `passed`,
  `errors`, `pass_rate`, `p95_latency_ms`, `max_tokens_per_case`, `thresholds`
  (a dict of the three bar numbers), `met`, `reasons`.
- Each entry of `document["cases"]`: `candidate`, `suite`, `case_id`, `prompt`,
  `completion`, `passed`, `score`, `detail`, `latency_ms`, `prompt_tokens`,
  `completion_tokens`, `attempts`, `error`, `finish_reason`, `total_tokens`,
  `errored`.
- `write_results(path, document)`, `read_results(path)`, `write_report(path, document)`,
  `render_report(document)`, and `ReportError`.
- Render helpers you should reuse rather than re-invent: `_esc(value)` (escape every
  value that comes from the document), `_percent(fraction)`, `_ms(value)`,
  `_badge(met)`, `_measure(measured, bar)`, `_table(headers, rows, *, cls="",
  row_classes=None)` (cells are inserted verbatim, so escape them first), and
  `_reasons(reasons)`.
- CSS classes already shipped, ready to use: `details`/`summary`, `.completion`
  (pre-wrapped, scrolling), `.error`, `.case-fail`, `.muted`, `.mono`, `.hash`,
  `.bar`, `.badge` with `.pass`/`.fail`, and `.missed` for a table row.
- **The anchor both code tasks use:** `render_report` builds a local list called
  `sections` holding three calls (`_header`, `_freeze_banner`, `_scoreboard`) and
  joins them. Adding a section means writing one function and adding one entry to
  that list — nothing else in `render_report` changes.
- `tests/test_report.py`: helpers `make_outcome(...)`, `make_results(...)`,
  `make_verdict(...)`, `make_freeze(status)`, `make_document(...)` and the constants
  `GENERATED_AT`, `STARTED_AT`, `FINISHED_AT`, `FROZEN_HASH`, `CURRENT_HASH`. Each
  defaults everything, so a test names only what it varies. Use them.

**Commit** the source files you changed, by name. Never `git add .` — the repo has
untracked loop scratch (`.plan-stamps/`, `plan.log`) that must never be committed.

## §E1 — the per-case drill-down: show the actual completions

**Files:** `src/bakeoff/report.py` (add one function below `_scoreboard`, plus one
entry in the `sections` list of `render_report`) and `tests/test_report.py` (append a
new class at the end).

**Pattern files:** `summarize` in `src/bakeoff/scoring.py` for grouping a flat list by
`(suite, candidate)` in first-seen order, and `_scoreboard` in `report.py` for
building a list of cells and handing it to `_table`.

SPEC.md feature 6 promises "per-case drill-down with the actual completions". Add
`_case_drilldown(document)` returning a `<section>` with an `<h2>Cases</h2>` heading
and one `<details>` block per suite × candidate pair, in the order the cases appear
in `document["cases"]`.

- The `<summary>` names the suite and the candidate and how many of its cases passed
  (for example `smoke / stub — 4 of 5 passed`).
- Inside each block, one `_table` row per case with: case id, a `_badge` for
  `passed`, the latency via `_ms`, the case's `total_tokens`, the completion text
  wrapped in `<span class="completion">…</span>`, and the case's `detail`.
- A case whose `errored` is true shows its `error` text in `<span class="error">…`
  instead of a completion.
- Give a failing case's row the class `case-fail` via `_table`'s `row_classes`.
- Escape every value from the document with `_esc` — a completion is untrusted text.

Then add `_case_drilldown(document)` to the `sections` list, after `_scoreboard`.

**Tests** (new class `TestCaseDrilldown`), asserting:

1. the rendered page contains a `<details>` block naming the suite and the candidate;
2. every case id in the document appears in the page;
3. the actual completion text of a case appears in the page;
4. a completion of `<b>hi</b>` is escaped — `&lt;b&gt;` is present and `<b>hi</b>` is
   not;
5. a case built with `make_outcome(error="boom")` shows `boom` and is marked
   `case-fail`.

**Gate:** the five commands in §E0.

## §E2 — the spend table: latency percentiles and token spend per candidate

**Files:** `src/bakeoff/report.py` (add one function below `_case_drilldown`, plus one
entry in the `sections` list) and `tests/test_report.py` (append a new class at the
end).

**Pattern file:** `_scoreboard` in `report.py` — same shape: gather rows, call
`_table`, wrap in a `<section>`.

SPEC.md feature 6 also promises "latency percentiles, token spend". Add
`_spend(document)` returning a `<section>` with an `<h2>Spend</h2>` heading and one
row per candidate, in first-seen order over `document["cases"]`, with columns:
candidate, cases, errors, prompt tokens, completion tokens, total tokens, p50
latency, p95 latency, slowest.

- Percentiles come from `percentile` in `src/bakeoff/scoring.py` — import it
  alongside the `exit_code` import already at the top of `report.py`. p50 is
  `percentile(latencies, 0.5)`, p95 is `percentile(latencies, 0.95)`; the slowest is
  plain `max(...)`. Never hand-roll a percentile.
- Token columns are plain sums of `prompt_tokens`, `completion_tokens` and
  `total_tokens` over that candidate's cases.
- Format every latency with `_ms` and escape every value with `_esc`.
- A document with no cases renders `<p class="muted">No cases were run.</p>` instead
  of a table — do not let `max()` raise on an empty list.

Then add `_spend(document)` to the `sections` list, after `_case_drilldown`.

**Tests** (new class `TestSpend`), asserting:

1. a two-candidate document renders two spend rows, one naming each candidate;
2. the total-token cell equals the hand-summed total of the outcomes you built;
3. the p95 cell equals `_ms(percentile([...], 0.95))` for those same latencies —
   import `percentile` in the test and compare, do not hard-code a number;
4. a document built with `outcomes=[]` and `verdicts=[]` renders `No cases were run`
   and does not raise;
5. the page still contains the scoreboard section — you added a section, you did not
   replace one.

**Gate:** the five commands in §E0.

## §E3 — the REBARRED report, from a bar edited on disk

**Files:** `tests/test_report.py` only (append a new class at the end). No source
changes.

**Pattern file:** `TestRebarredEndToEnd` in `tests/test_freeze.py` — it copies the
example manifest's text into `tmp_path`, freezes it, edits the bar and re-loads. Copy
that setup; the assertions here are about the *page*, not the check.

`TestFreezeBanner` already proves the branding from a hand-built `FreezeCheck`. This
class proves it the way a user meets it: a real manifest, frozen, then edited, and
the resulting report.

In one `tmp_path`: write `Path("examples/quickstart/audition.yaml").read_text()` to
`tmp_path / "audition.yaml"`; use `load_manifest` (not `load_audition` — no suite
directories are copied and the freeze is about the bar alone); freeze it with
`freeze_bar` + `write_lockfile(lockfile_path(path), ...)`; then rewrite the file text
with `min_pass_rate: 0.8` replaced by `min_pass_rate: 0.5` (that string appears
exactly once) and re-load. Build the check with `check_freeze(manifest.bar,
find_lockfile(path))` and pass it to `make_document(freeze=check)`.

**Tests** (new class `TestRebarredReport`), asserting:

1. the report of the *frozen* manifest contains `FROZEN` and does not contain
   `REBARRED`;
2. after the edit, the report contains `REBARRED`;
3. it contains both the lockfile's `bar_hash` and the current `check.current_hash`,
   and those two strings differ;
4. it also names `--rebar`, so a reader learns how the run was allowed;
5. rendering the same rebarred document twice gives identical strings.

**Gate:** the five commands in §E0.

## §E4 — the self-containment promise, asserted

**Files:** `tests/test_report.py` only (append a new class at the end). No source
changes.

**Pattern file:** `TestRenderReport` in this same file — same helpers, one plain
assertion per behaviour.

DECISIONS.md and SPEC.md both fence this: the report is one file with zero external
requests. A test is the only thing that keeps it true as sections are added.

Build the page from the default helpers (`make_document(...)` with the default
prompts and completions, which contain no URLs), then assert the markers are absent.
Keep the URL case separate — a completion that *mentions* a URL is fine as escaped
text; what must never appear is a link or a fetch.

**Tests** (new class `TestSelfContained`), asserting:

1. the rendered page contains none of `http://`, `https://`, `<script`, `<link`,
   `@import` or `url(` — assert each with a plain `not in`;
2. the page contains exactly one `<style>` block (`html.count("<style>") == 1`);
3. rendering the same document twice returns identical strings;
4. writing the document with `write_results` and reading it back with `read_results`
   renders a string identical to rendering the original document — a re-render never
   changes what the report says;
5. a case whose completion is `see http://example.com/x` renders that text escaped
   into the page with no `<a ` anchor tag anywhere.

**Gate:** the five commands in §E0.

## §E5 — the whole pipeline on disk, against the bundled stub

**Files:** `tests/test_report_end_to_end.py` (new file). No source changes.

**Pattern files:** `TestRunAuditionEndToEnd` in `tests/test_runner.py` for the
`with run_stub() as base_url:` shape and for pointing the quickstart candidate at that
URL, and `TestQuickstartFreeze` in `tests/test_examples.py` for the `EXAMPLES_DIR` /
`AUDITION_PATH` constants. No network is touched: the stub binds a random localhost
port.

One class, `TestReportEndToEnd`, that runs the real pipeline once per test: load the
quickstart audition, point candidate 0 at the stub's base URL, `run_audition`,
`summarize`, `judge` against `audition.manifest.bar`, `check_freeze` against
`find_lockfile(AUDITION_PATH)`, then `results_document(..., manifest="audition.yaml",
generated_at=...)` with a fixed timestamp string, and write both artefacts into
`tmp_path` with `write_results` and `write_report`.

A private helper method on the class that does the run and returns the document keeps
each test short — mirror `_load_quickstart` in `tests/test_runner.py`.

**Tests** (new class `TestReportEndToEnd`), asserting:

1. the document has five cases, one pair, `met_bar` true and `exit_code` 0;
2. `read_results(tmp_path / "results.json")` equals the document that was written;
3. the document's `freeze["status"]` is `"frozen"` — the shipped lockfile still
   matches the shipped bar;
4. the written `report.html` names the candidate `stub`, the suite `smoke`, and every
   case id of the smoke suite;
5. the written page contains `FROZEN` and does not contain `REBARRED`;
6. re-rendering from the file on disk (`render_report(read_results(...))`) equals the
   text of the written `report.html`.

**Gate:** the five commands in §E0.

## §E6 — close the phase

**Files:** `STATUS.md` (append) and `ROADMAP.md` (edit rows).

Run `bash verify.sh`. All five gates must be green before you touch either doc; if one
is red, fix it first — that is the task.

Then append a `## Phase E` section to `STATUS.md`, mirroring the `## Phase D` section
directly above it: two or three sentences naming what shipped (the report module,
`results.json` and its reader, the HTML page with the freeze banner and scoreboard,
the per-case drill-down, the spend table, the REBARRED and self-containment proofs,
the end-to-end pipeline test) and one sentence naming what is still missing (the CLI
and `docs/PROCESS.md`).

Then in `ROADMAP.md`:

- row 6 (*Report*): status `SHIPPED`, phase `E`, note that `results.json`, the
  self-contained HTML page and the REBARRED branding are built, and that the README
  hero screenshot still needs a human with a browser;
- row 9 (*Deploy-grade packaging*): keep it `PARTIAL`, and add to its note that the
  README quickstart and `docs/PROCESS.md` are what is left;
- append to the reservations ledger at the bottom: the report is rendered from
  `results.json` alone and never re-dates it, so `bakeoff report` is a re-render, not
  a re-run (§E0); and wiring the two artefacts to real paths — where `results.json`
  and `report.html` get written, and the `--rebar` flag — belongs to the CLI phase
  (§E5).

Do not edit any other row and do not rewrite the file.

**Gate:** `bash verify.sh` green, then commit both docs.
