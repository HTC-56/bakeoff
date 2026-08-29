#!/usr/bin/env bash
# live-check.sh — the human-run real-endpoint proof.
#
# This script proves bakeoff works against a real OpenAI-compatible endpoint.
# It is the only thing in the repo that touches a network. CI never runs it;
# verify.sh never runs it.
#
# Set $BAKEOFF_BASE_URL (the model server) and $BAKEOFF_MODEL (the model id),
# then run this script. With either unset it prints usage and exits non-zero.
#
# Examples (documentation only — uses RFC 5737 addresses):
#   BAKEOFF_BASE_URL=http://192.0.2.10:8000 BAKEOFF_MODEL=gpt-4o bash live-check.sh
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0

report() {
  fail=1
  printf '\nlive-check: %s\n%s\n' "$1" "$2"
}

# --- usage: both variables must be set ---
if [ -z "${BAKEOFF_BASE_URL:-}" ] || [ -z "${BAKEOFF_MODEL:-}" ]; then
  cat <<EOF
Usage:
  BAKEOFF_BASE_URL=<endpoint> BAKEOFF_MODEL=<model-id> bash scripts/live-check.sh

Required environment variables:
  BAKEOFF_BASE_URL  — the OpenAI-compatible endpoint (e.g. http://localhost:8000)
  BAKEOFF_MODEL     — the model identifier to audition
EOF
  exit 1
fi

# --- scaffold a throwaway audition ---
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

uv run bakeoff init "$tmpdir" 2>&1
if [ $? -ne 0 ]; then
  report "bakeoff init failed" "Check the message above."
  exit "$fail"
fi

# --- point it at the real endpoint ---
sed -i "s|base_url:.*|base_url: $BAKEOFF_BASE_URL|" "$tmpdir/audition.yaml"
sed -i "s|model:.*|model: $BAKEOFF_MODEL|" "$tmpdir/audition.yaml"

# --- freeze then run ---
uv run bakeoff freeze "$tmpdir/audition.yaml" 2>&1
uv run bakeoff run "$tmpdir/audition.yaml" 2>&1
exit $?
