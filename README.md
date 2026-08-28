# bakeoff

Model selection by pre-registered audition, not vibes. Declare the candidate models,
the task suites, the graders, and the pass bar before any model runs; then the runner
produces a scored report an engineer can re-execute and a manager can read. The freeze
mechanic is the centerpiece: a bar edited after results exist is branded on the report,
not hidden.

## Status

Early — built phase by phase by an autonomous coding loop. The CLI and the report are
not built yet.

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
