#!/usr/bin/env bash
# verify.sh — Phase A gate composition.
#
# Runs the five gates from §A0 in order, prints a banner before each,
# collects failures, and exits 1 if any gate failed. Every gate runs
# even when an earlier one fails so the user sees the full picture at
# a glance.
#
# Gates (in order): ruff check, ruff format, mypy, pytest, scrub-check.
set -uo pipefail
cd "$(dirname "$0")"

fail=0
total=0
pass=0

report() {
  fail=1
  printf '  FAIL: %s\n' "$1"
}

run_gate() {
  local label="$1"
  shift
  total=$((total + 1))
  printf '\n===== %s =====\n' "$label"
  if "$@" >/dev/null 2>&1; then
    printf '  ok\n'
    pass=$((pass + 1))
  else
    report "$label"
  fi
}

run_gate "ruff check"       uv run ruff check .
run_gate "ruff format"      uv run ruff format --check .
run_gate "mypy"             uv run mypy
run_gate "pytest"           uv run pytest
run_gate "scrub-check"      bash scripts/scrub-check.sh

printf '\n===== %d/%d gates passed =====\n' "$pass" "$total"

if [ "$fail" -ne 0 ]; then
  printf 'verify: FAILED — %d of %d gates did not pass\n' "$((total - pass))" "$total"
  exit 1
fi

printf 'verify: all %d gates passed\n' "$total"
exit 0
