# bakeoff

Model selection by pre-registered audition, not vibes. Declare the candidate models,
the task suites, the graders, and the pass bar before any model runs; then the runner
produces a scored report an engineer can re-execute and a manager can read. The freeze
mechanic is the centerpiece: a bar edited after results exist is branded on the report,
not hidden.

## Status

Built phase by phase by an autonomous coding loop. The CLI (`init`, `validate`,
`freeze`, `run`, `report`), all five graders (`exact`, `contains`, `regex`,
`numeric_tolerance`, `json_schema`), the runner (retries, backoff, per-candidate
concurrency), the freeze mechanic (bar hashing, REBARRED branding), and the
self-contained HTML report are all built and gated against the bundled stub.

Two things are not: a hero screenshot (it needs a human with a browser) and any claim
that a real, non-stub endpoint was audited — `scripts/live-check.sh` is run by a human,
not by CI.

## Quickstart

Get a working report in two minutes with the bundled stub:

```
uv sync
```

Start the stub in a second terminal:

```
uv run python -m bakeoff.stub --port 8000
```

Scaffold your audition:

```
uv run bakeoff init myaudition
```

Freeze the bar:

```
uv run bakeoff freeze myaudition/audition.yaml
```

Run the audition:

```
uv run bakeoff run myaudition/audition.yaml
```

Open `report.html` — a self-contained HTML file with the scoreboard, case drilldowns,
and token spend summary.

## The freeze mechanic

The freeze mechanic is bakeoff's whole point. Here is the honesty story:

```
# Freeze the bar …
uv run bakeoff freeze myaudition/audition.yaml

# … then edit it on disk
sed -i 's/min_pass_rate: 0.8/min_pass_rate: 1.0/' myaudition/audition.yaml

# The runner refuses to proceed — exit 2
uv run bakeoff run myaudition/audition.yaml

# Run anyway with --rebar; the report is branded REBARRED
# with both hashes so anyone can see the bar moved
uv run bakeoff run --rebar myaudition/audition.yaml
```

The report produced by `--rebar` carries both the frozen bar hash and the bar hash
that was actually used. There is no way to quietly change the bar after results exist.

## Requirements

Python 3.12+ and [uv](https://github.com/astral-sh/uv).

## Development

```
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
bash scripts/scrub-check.sh
```

All five must be green before any change lands.

## Running the bundled stub

```
uv run python -m bakeoff.stub --port 8000
```

The test suite starts its own stub on a random port, so the whole suite runs with no
model and no network.
