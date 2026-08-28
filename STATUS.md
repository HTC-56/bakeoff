# Status

Repo scaffolded 2026-08-27. Nothing built yet. SPEC.md is the product;
DECISIONS.md locks the fence; ROADMAP.md is the scoreboard. The planning lane
authors Phase A from SPEC.md (Phase A must prove the toolchain — uv, ruff,
mypy --strict, pytest — plus one grader and the bundled stub server
end-to-end before anything else is built; this is the executor's first
Python repo).

Per-phase sections append below as phases ship.

## Phase A

Phase A shipped the toolchain (uv, ruff, mypy --strict, pytest), four graders
(`grade_exact`, `grade_contains`, `grade_regex`, `grade_numeric_tolerance`), the
HTTP seam in the bundled stub server (including the `error_status` switch),
`scrub-check.sh`, CI, `README.md`, and `verify.sh`. Still missing: the audition
manifest, the bar and freeze mechanic, the runner, the report, the CLI.
