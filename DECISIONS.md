# Decisions

## Locked (2026-08-27, at scaffold)

- **SPEC.md is the whole product.** v1 is the nine features there, fenced by
  its non-goals. The planning lane derives phases from SPEC.md only; it never
  invents features. When every SPEC.md feature is built and gated,
  "PROJECT SPEC COMPLETE" is the desired terminal state — declare it, do not
  find more work. This project is meant to FINISH.
- **Stack**: Python 3.12+ (CI pins 3.12), uv, ruff (lint + format),
  mypy --strict, pytest. Dependencies exactly: httpx, pydantic, PyYAML,
  jsonschema, click. src layout (`src/bakeoff/`). Strictness is never
  weakened to pass a gate — a task that cannot pass strict mypy is
  respecced and the reason recorded here.
- **The freeze mechanic is pre-registered** (SPEC.md feature 4): bar hashed
  into a lockfile before any run; a post-freeze bar edit runs only with
  `--rebar` and the report brands it REBARRED with both hashes. This is the
  product's whole point; no task may soften it.
- **Seam is pre-registered**: one client module owns all HTTP; the bundled
  stub is the only endpoint tests and the quickstart touch; CI makes no
  network calls. `scripts/live-check.sh` (not CI) is the real-endpoint
  proof.
- **First Python repo for the executor**: Phase A proves the toolchain + one
  grader + the stub end-to-end before anything else. Structural failure at
  the stack is recorded here and the lane stands down; PROCESS.md reports it
  honestly.
- **Gates**: ruff check + format --check, mypy, pytest, scrub-check — all
  green at every phase end. `verify.sh` composes them plus the
  README-quickstart lint.
- **Public-repo discipline from commit 1**: this repo will be published. No
  private hostnames, no real LAN IPs (docs use `localhost` / `192.0.2.x`),
  no absolute home paths, no key material, no references to other private
  projects — in files AND commit messages. The public HTC-56 repos may be
  named. `scrub-check.sh` enforces the file half; sessions carry the
  commit-message half.
- **Neutral git identity** until the publish decision (human-gated).

## Human-gated (never resolved by the loop)

- Publishing: flipping the repo public, name confirmation, license choice
  (default intent: MIT).
- Any claim that a real (non-stub) audition ran — live-check.sh is run by a
  human.
- Any scope beyond SPEC.md v1.

## Open Questions

*(none — SPEC.md answers v1 in full)*
