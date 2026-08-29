# PROJECT SPEC COMPLETE

The loop has finished every piece of work SPEC.md authorizes. All nine v1 feature
rows in `ROADMAP.md` read SHIPPED, `bash verify.sh` reports 6/6, `uv run pytest` is
195 tests green with no network, and GitHub Actions is green on `main`.

This is the terminal state. Per DECISIONS.md ("this project is meant to FINISH"), the
planning lane is stopping rather than inventing scope. `TODO.md` has no open tasks and
none will be added.

Shipped: **A** toolchain + graders + stub · **B** manifest, suites, quickstart example ·
**C** runner, scoring, JSONL ledger · **D** freeze, lockfile, REBARRED · **E** the
self-contained HTML report · **F** the CLI + `docs/PROCESS.md` · **G** the stranger's
path, `live-check.sh`, the CI badge. See `ROADMAP.md` for per-feature coverage and
`STATUS.md` for the per-phase detail — this file does not restate them.

## What needs a human

1. **Publish decision.** Flip the repo public, confirm the name, pick a license
   (DECISIONS.md records default intent: MIT). *Unlocks:* the README CI badge renders
   for strangers (it is committed and correct, but a private repo serves it broken),
   and the commit history — which SPEC.md calls part of the deliverable — becomes
   readable.
2. **The README hero screenshot.** Run the quickstart, open `report.html` in a
   browser, screenshot it, commit it, and reference it from `README.md`. *Unlocks:* the
   last clause of SPEC.md feature 6. No loop session can do this; there is no browser.
3. **The real-endpoint proof.** Run `scripts/live-check.sh` with `$BAKEOFF_BASE_URL`
   and `$BAKEOFF_MODEL` against a real OpenAI-compatible endpoint. *Unlocks:* the right
   to claim in README/PROCESS.md that a non-stub audition ran. The script is written and
   has never been executed — DECISIONS.md reserves that claim for a human, and CI never
   makes a network call.
4. **Any scope beyond SPEC.md v1.** The loop will not resume on its own. New scope must
   be locked in DECISIONS.md first; until then this file stands.
