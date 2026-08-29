#!/usr/bin/env bash
# readme-lint.sh — every bakeoff command the README shows must exist.
#
# Two checks against README.md:
#   1. Every `bakeoff <subcommand>` is a real click command.
#   2. Every `python -m bakeoff.<module>` names an existing module file.
#
# Exits non-zero on any hit.

set -uo pipefail
cd "$(dirname "$0")/.."

fail=0

report() {
  fail=1
  printf '\nreadme-lint: %s\n%s\n' "$1" "$2"
}

# 1. Every bakeoff <subcommand> shown in the README is a real command.
while IFS= read -r line; do
  subcmd="${line#bakeoff }"
  if ! uv run bakeoff "$subcmd" --help >/dev/null 2>&1; then
    report "unknown command: bakeoff $subcmd" "$line"
  fi
done < <(grep -oE '\bbakeoff [a-z]+' README.md | sort -u)

# 2. Every python -m bakeoff.<module> names a module that exists.
while IFS= read -r line; do
  module="${line#python -m bakeoff.}"
  if [ ! -f "src/bakeoff/${module}.py" ]; then
    report "missing module: $module" "$line"
  fi
done < <(grep -oE 'python -m bakeoff\.[a-z]+' README.md | sort -u)

if [ "$fail" -ne 0 ]; then
  printf '\nreadme-lint FAILED — commands or modules above are missing.\n'
  exit 1
fi

printf 'readme-lint: clean (%s commands/modules checked)\n' \
  "$(cat <(grep -oE '\bbakeoff [a-z]+' README.md | sort -u) \
         <(grep -oE 'python -m bakeoff\.[a-z]+' README.md | sort -u) \
         | sort -u | wc -l | tr -d ' ')"
