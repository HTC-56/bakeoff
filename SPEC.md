# bakeoff — v1 spec

Model selection by pre-registered audition, not vibes. Declare the candidate
models, the task suites, the graders, and the pass bar BEFORE any model runs;
then the runner produces a scored report an engineer can re-execute and a
manager can read. The freeze mechanic is the centerpiece: a bar edited after
results exist is branded on the report, not hidden. Built end-to-end by an
autonomous local-model coding loop; the commit history is part of the
deliverable (see `docs/PROCESS.md` when it lands). Works against any
OpenAI-compatible endpoint — e.g. a
[local-ai-gateway](https://github.com/HTC-56/local-ai-gateway) fronting a
local model fleet.

## v1 features (all of these, nothing more)

1. **The audition manifest (YAML).** Candidates (name, OpenAI-compatible
   base URL, model id, per-candidate profile: system prompt, temperature,
   max tokens, concurrency cap), task suites, and the bar — one file,
   validated by pydantic with errors that name the field and the fix.
2. **Task suites as files.** A suite is a directory of cases; a case = input
   prompt + grader spec + optional reference answer. No hidden registry —
   `ls` shows the audition.
3. **Pure graders, unit-tested:** exact, contains, regex, json-schema,
   numeric-tolerance. Each grader is a pure function; grader bugs are test
   failures, not audit noise.
4. **The pre-registered bar + freeze.** Per suite × candidate thresholds
   (min pass rate, max p95 latency, max tokens/case). `bakeoff freeze`
   hashes the bar into a lockfile; `bakeoff run` records bar-hash-at-run.
   A run whose bar no longer matches its freeze runs only with `--rebar`,
   and the report brands it REBARRED with both hashes. Honesty is a
   mechanism, not a promise.
5. **The runner.** Async httpx against `/v1/chat/completions`; retries with
   backoff, timeouts, per-candidate concurrency; captures score, latency,
   and `usage` tokens per case; refusals, timeouts, and malformed replies
   are first-class recorded outcomes, never crashes.
6. **The report.** One self-contained HTML file (inline CSS/JS, no CDN, no
   web fonts, no framework): scoreboard vs bar, per-case drill-down with the
   actual completions, latency percentiles, token spend. Plus
   `results.json` (machine-readable) and exit code 0/1 = bar met/failed —
   an audition drops into CI as a model regression test. The README hero
   screenshot.
7. **The CLI:** `init` (writes a working example manifest + suite),
   `validate`, `freeze`, `run`, `report` (re-render from results.json —
   rendering is pure: same results in, same report out).
8. **The bundled stub.** An in-repo stub OpenAI-compatible server with
   canned completions and usage counts: the test suite runs against it (CI
   needs no model), and the README quickstart audits the stub so a stranger
   sees a full real report in two minutes with nothing installed but Python.
9. **Deploy-grade packaging.** `pyproject.toml` + uv; ruff (lint + format)
   + mypy --strict + pytest; JSONL run ledger; GitHub Actions CI; README
   quickstart (stub audition, then a real endpoint); `docs/PROCESS.md`.

## Pre-registered rules

- Toolchain: Python 3.12+ (CI pins 3.12), uv, ruff, mypy --strict, pytest.
  All four green is the gate; strictness is not relaxed to make a task pass —
  a task that cannot pass strict mypy is respecced, recorded in DECISIONS.md.
- Seam: every HTTP call goes through one client module; tests and the
  quickstart run against the bundled stub; CI makes no network calls.
  `scripts/live-check.sh` (not CI) proves the same paths against a real
  OpenAI-compatible endpoint and gates any claim that a real audition ran.
- Dependencies are named in full: httpx, pydantic, PyYAML, jsonschema,
  click. A task that adds anything else must name it and why.
- First Python repo for the build loop: Phase A proves the toolchain + one
  grader + the stub server end-to-end before anything else is built. If the
  executor fails structurally at Python, that is recorded in DECISIONS.md
  and PROCESS.md reports it honestly.

## Non-goals (v1 refuses these)

- No LLM-as-judge grading — v1 graders are mechanical only. (The honest
  version of judge-grading needs its own pre-registered design; bolting it
  on cheap would undercut the whole story.)
- No provider SDKs, no per-vendor adapters — OpenAI-compatible HTTP only.
- No server, no dashboard process — the report is a static file; the CLI is
  the product.
- No dollar-cost math (tokens only), no model downloading or management,
  no plugin system, no resume-interrupted-runs, no notebooks.

## Stack & shape

- Layout: `src/bakeoff/` (manifest, graders, runner, client, stub, report,
  cli), `tests/`, `examples/` (quickstart manifest + suites), `scripts/`
  (scrub-check.sh, live-check.sh), `docs/PROCESS.md`.

## Gates

- `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy` +
  `uv run pytest` green at every phase end.
- `bash scripts/scrub-check.sh` green from phase 1: greps the tree for
  private hostnames, non-documentation IPs, absolute home paths, and key
  material. Docs use `localhost` and `192.0.2.x` only.
- `verify.sh` = all of the above + README-quickstart lint (commands shown
  in the README must exist in the repo).

## Done means

A stranger with uv: `uv sync && uv run pytest` green with no model server
and no network. The README quickstart runs `bakeoff init`, freezes the bar,
audits the bundled stub, and opens a real report. Editing the bar after the
freeze and re-running with `--rebar` produces a visibly REBARRED report —
the honesty mechanic demonstrated, not described. Pointed at any
OpenAI-compatible endpoint, the same manifest audits real models
(live-check.sh). Exit codes make it CI-usable. CI badge green. PROCESS.md
tells the story in one page.
