#!/usr/bin/env bash
# scrub-check.sh — the public-repo gate.
#
# This repo will be published. Greps every git-tracked file for the four things that
# must never leave a private machine: absolute home paths, real host addresses,
# private hostnames, and key material. Exits non-zero on any hit.
#
# Patterns are written with single-character classes (/ho[m]e/) so that this script
# scans itself honestly instead of being excluded from its own check.
#
# Address policy: documentation uses localhost, 127.0.0.1, and the RFC 5737
# documentation range 192.0.2.x. Every other IPv4 literal is a finding.
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0

# Never pipe into the reporter: a function on the right of a pipe runs in a subshell,
# where setting fail=1 is lost and the gate passes while printing findings.
report() {
  fail=1
  printf '\nscrub-check: %s\n%s\n' "$1" "$2"
}

scan() {
  local label="$1" pattern="$2"
  local hits
  hits="$(git ls-files -z | xargs -0 grep -nEI -- "$pattern" 2>/dev/null || true)"
  if [ -n "$hits" ]; then
    report "$label" "$hits"
  fi
}

scan "absolute home path"      '/ho[m]e/[a-z]|/Us[e]rs/[a-z]'
scan "private hostname"        '[a-z0-9-]+\.(l[a]n|int[e]rnal|localdo[m]ain)\b'
scan "mDNS hostname"           '[a-z0-9-]+\.lo[c]al([^./a-zA-Z0-9]|$)'
scan "private key material"    '-----BEG[I]N [A-Z ]*PRIVATE KEY-----'
scan "api key or token"        '\b(s[k]-[A-Za-z0-9]{20,}|g[h]p_[A-Za-z0-9]{20,}|AK[I]A[0-9A-Z]{16})\b'

# IPv4 literals, minus the three addresses documentation is allowed to use.
ip_hits="$(git ls-files -z \
  | xargs -0 grep -nEI -- '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b' 2>/dev/null \
  | grep -vE '\b(127\.0\.0\.1|0\.0\.0\.0|192\.0\.2\.[0-9]{1,3})\b' || true)"
if [ -n "$ip_hits" ]; then
  report "non-documentation IP address" "$ip_hits"
fi

if [ "$fail" -ne 0 ]; then
  printf '\nscrub-check FAILED — this repo is public; scrub the findings above.\n'
  exit 1
fi

printf 'scrub-check: clean (%s tracked files)\n' "$(git ls-files | wc -l | tr -d ' ')"
