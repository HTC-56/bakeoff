"""The command line — the product a user actually types.

SPEC.md feature 7: five commands over the modules the earlier phases built.

``init``      write a working example manifest and suite (:mod:`bakeoff.templates`)
``validate``  load a manifest and every suite it names, and say what is in it
``freeze``    hash the bar into a lockfile beside the manifest
``run``       ask every candidate every case, score it, write both artefacts
``report``    re-render the HTML from ``results.json`` — a re-render, never a re-run

Two rules shape this module, and every command must keep them.

**Exit codes carry meaning**, because an audition is meant to drop into CI as a model
regression test:

* ``0`` — the command worked; for ``run``, every pair cleared the bar.
* ``1`` — ``run`` finished and at least one pair missed the bar. Not an error: a
  verdict. This is :func:`bakeoff.scoring.exit_code`.
* ``2`` — the audition is misconfigured: a manifest that will not load, a bar that
  was never pre-registered, a bar that has moved since its freeze. Something to fix,
  not a result.

**A misconfiguration prints its message, never a traceback.** Every loader in bakeoff
raises a subclass of :class:`~bakeoff.errors.ConfigError` whose text already names the
file, the field and the fix, so commands wrap their loading in :func:`fixable` and let
that message be the whole output.

This module owns no logic of its own: it loads, calls, prints, and exits. Anything a
test would want to assert on the *numbers* of belongs in the module that computed them.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import click

from . import __version__
from .errors import ConfigError
from .freeze import (
    FreezeCheck,
    check_freeze,
    find_lockfile,
    freeze_bar,
    lockfile_path,
    require_freeze,
    write_lockfile,
)
from .ledger import LEDGER_FILENAME, append_run, run_record
from .manifest import Audition, load_audition
from .report import read_results, results_document, write_report, write_results
from .runner import run_audition_sync
from .scoring import PairVerdict, exit_code, judge, summarize
from .templates import write_scaffold

DEFAULT_MANIFEST = "audition.yaml"
"""What every command assumes when the user names no manifest."""

DEFAULT_RESULTS = "results.json"
DEFAULT_REPORT = "report.html"

CONFIG_EXIT_CODE = 2
"""Exit code for an audition that is misconfigured — distinct from a missed bar (1)."""

_MANIFEST_ARGUMENT = click.argument(
    "manifest",
    default=DEFAULT_MANIFEST,
    type=click.Path(dir_okay=False, path_type=Path),
)
"""The one positional argument four of the five commands take. Reuse it; do not retype it."""


class CliError(click.ClickException):
    """A misconfiguration the user can fix, printed as ``Error: <message>``.

    Exits :data:`CONFIG_EXIT_CODE` so a CI job can tell "the audition is broken" from
    "the audition ran and missed the bar".
    """

    exit_code = CONFIG_EXIT_CODE


@contextmanager
def fixable() -> Iterator[None]:
    """Re-raise any :exc:`~bakeoff.errors.ConfigError` as a :exc:`CliError`.

    Wrap every load, freeze check and freeze gate in this. The loaders' messages are
    already written for a human — this hands them over verbatim instead of letting a
    traceback reach the terminal.
    """
    try:
        yield
    except ConfigError as exc:
        raise CliError(str(exc)) from exc


def load(manifest: Path) -> Audition:
    """Load the manifest and every suite it names, or exit 2 with the reason."""
    with fixable():
        return load_audition(manifest)


def freeze_state(audition: Audition, manifest: Path) -> FreezeCheck:
    """Where this manifest's bar stands against the lockfile beside it."""
    with fixable():
        return check_freeze(audition.manifest.bar, find_lockfile(manifest))


def describe_freeze(check: FreezeCheck) -> str:
    """One line naming the freeze state, and both hashes when they disagree."""
    if check.frozen_hash is not None and check.frozen_hash != check.current_hash:
        return f"{check.status.value} — frozen: {check.frozen_hash}, current: {check.current_hash}"
    return f"{check.status.value} — {check.current_hash}"


def describe_verdict(verdict: PairVerdict) -> str:
    """One scoreboard line for one suite x candidate pair, as the terminal shows it."""
    summary = verdict.summary
    return (
        f"  {summary.suite} / {summary.candidate}: "
        f"{summary.passed}/{summary.cases} passed, "
        f"p95 {summary.p95_latency_ms:.0f}ms, "
        f"max {summary.max_tokens_per_case} tokens — "
        f"{'MET' if verdict.met else 'MISSED'}"
    )


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="bakeoff")
def main() -> None:
    """Model selection by pre-registered audition, not vibes.

    Declare the candidates, the suites, the graders and the pass bar before any model
    runs; freeze the bar; then run the audition and read the report. A bar edited
    after the freeze runs only with --rebar, and the report says so.
    """


@main.command()
@click.argument(
    "directory",
    default=".",
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing files in the target directory.",
)
def init(directory: Path, force: bool) -> None:
    """Write a working audition scaffold into *directory*.

    Creates ``audition.yaml`` and a ``suites/smoke/`` directory with five case
    files.  A separate ``bakeoff freeze`` is required to lock the bar.
    """
    paths = []
    with fixable():
        paths = write_scaffold(directory, force=force)
    for p in paths:
        click.echo(f"wrote {p}")
    click.echo("next steps:  bakeoff freeze audition.yaml  bakeoff run audition.yaml")


@main.command()
@_MANIFEST_ARGUMENT
def validate(manifest: Path) -> None:
    """Load the manifest and suites, print what is in the audition.

    Never fails on the freeze — an unfrozen manifest is still valid.
    """
    with fixable():
        audition = load(manifest)
    check = freeze_state(audition, manifest)
    candidates = audition.manifest.candidates
    total_cases = sum(len(s) for s in audition.suites)
    click.echo(
        f"{manifest.name}: {len(candidates)} candidate(s), "
        f"{len(audition.suites)} suite(s), {total_cases} case(s)"
    )
    for c in candidates:
        click.echo(f"  candidate: {c.name}  model={c.model}  base_url={c.base_url}")
    for s in audition.suites:
        click.echo(f"  suite: {s.name}  ({len(s)} case(s))")
    click.echo(f"  freeze: {describe_freeze(check)}")


@main.command()
@_MANIFEST_ARGUMENT
def freeze(manifest: Path) -> None:
    """Pre-register the bar in a lockfile beside the manifest.

    Always succeeds — deliberately re-registering a new bar is the honest move.
    """
    with fixable():
        audition = load(manifest)
    old_check = freeze_state(audition, manifest)
    lock = freeze_bar(audition.manifest, manifest_path=manifest)
    write_lockfile(lockfile_path(manifest), lock)
    click.echo(f"wrote {lockfile_path(manifest)}  {lock.bar_hash}")
    if old_check.status.value == "frozen" and old_check.frozen_hash == lock.bar_hash:
        click.echo("  bar unchanged — already frozen")
    elif old_check.frozen_hash is None:
        click.echo("  bar: new freeze")
    else:
        click.echo(f"  bar: moved from {old_check.frozen_hash}")


@main.command()
@_MANIFEST_ARGUMENT
@click.option(
    "--rebar",
    is_flag=True,
    help="Run even though the bar moved since the freeze. The report is branded REBARRED.",
)
@click.option(
    "--results",
    "results_path",
    default=DEFAULT_RESULTS,
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Where to write the machine-readable results.",
)
@click.option(
    "--report",
    "report_path",
    default=DEFAULT_REPORT,
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Where to write the self-contained HTML report.",
)
@click.option(
    "--ledger",
    "ledger_path",
    default=LEDGER_FILENAME,
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="JSONL run ledger this run is appended to.",
)
@click.pass_context
def run(
    ctx: click.Context,
    manifest: Path,
    rebar: bool,
    results_path: Path,
    report_path: Path,
    ledger_path: Path,
) -> None:
    """Run the audition and score it against the pre-registered bar.

    Exits 0 when every pair cleared the bar and 1 when any pair missed it, so an
    audition works as a CI regression test. Writes results.json, report.html, and one
    line to the run ledger.
    """
    audition = load(manifest)
    check = freeze_state(audition, manifest)
    with fixable():
        require_freeze(check, rebar=rebar)

    name = manifest.name
    click.echo(f"bakeoff run — {name}")
    click.echo(f"  freeze: {describe_freeze(check)}")

    results = run_audition_sync(audition)
    verdicts = judge(summarize(results.outcomes), audition.manifest.bar)
    document = results_document(results, verdicts, manifest=name, freeze=check)

    write_results(results_path, document)
    write_report(report_path, document)
    append_run(ledger_path, run_record(results, verdicts, manifest=name, freeze=check))

    for verdict in verdicts:
        click.echo(describe_verdict(verdict))
        for reason in verdict.reasons:
            click.echo(f"      {reason}")

    click.echo(f"wrote {results_path} and {report_path}")
    code = exit_code(verdicts)
    click.echo("bar met" if code == 0 else "bar MISSED")
    ctx.exit(code)


@main.command()
@click.argument(
    "results_path",
    metavar="[RESULTS]",
    default=DEFAULT_RESULTS,
    type=click.Path(dir_okay=False, path_type=Path),
)
@click.option(
    "--out",
    "report_path",
    default=DEFAULT_REPORT,
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Where to write the HTML report.",
)
def report(results_path: Path, report_path: Path) -> None:
    """Re-render the HTML report from a results.json.

    Rendering is pure — the same results in produce the same report out — so this is
    a re-render and never a re-run. No model is contacted.
    """
    with fixable():
        document = read_results(results_path)
    write_report(report_path, document)
    click.echo(f"wrote {report_path} from {results_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
