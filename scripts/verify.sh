#!/usr/bin/env bash
# verify.sh — compose the six gates, report pass/fail count.
#
# Runs the five toolchain gates (§A0) plus readme-lint and prints
# "N/6 gates passed". Exits non-zero if any gate fails.
set -uo pipefail
cd "$(dirname "$0")/.."

pass=0
total=6

ok() { pass=$((pass + 1)); }

run_gate() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    ok
  else
    printf '%s: FAILED\n' "$label"
  fi
}

run_gate "ruff check"     uv run ruff check .
run_gate "ruff format"    uv run ruff format --check .
run_gate "mypy"           uv run mypy
run_gate "pytest"         uv run pytest
run_gate "scrub-check"    bash scripts/scrub-check.sh
run_gate "readme-lint"    bash scripts/readme-lint.sh

printf '%d/%d gates passed\n' "$pass" "$total"

if [ "$pass" -ne "$total" ]; then
  exit 1
fi
