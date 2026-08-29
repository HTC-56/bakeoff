"""CLI tests: drive the real commands in-process, against the bundled stub.

Every test here runs the command a user would type. Nothing is mocked except the
endpoint, which is the bundled stub on a random localhost port — no network call is
ever made.

The helpers at the top are the whole harness; a new command's test class should use
them rather than build its own:

* :func:`invoke` — run the CLI and get click's ``Result`` back. It never raises, so a
  test asserts on ``result.exit_code`` and ``result.output``.  ``result.output`` holds
  stdout *and* stderr, so an ``Error: ...`` message is asserted on the same way as a
  normal line.
* :func:`copy_quickstart` — the shipped ``examples/quickstart`` tree copied into a
  writable directory, so a test can edit a manifest without touching the repo.
* :func:`quickstart_against_stub` — the same copy with its candidate pointed at a
  running stub, which is what any test of ``run`` needs.

Exit codes are the contract these tests exist to pin: 0 worked, 1 the bar was missed,
2 the audition is misconfigured.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from click.testing import CliRunner, Result

from bakeoff.cli import CONFIG_EXIT_CODE, main
from bakeoff.stub import run_stub

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples" / "quickstart"
PLACEHOLDER_URL = "http://localhost:8000"


def invoke(*args: str) -> Result:
    """Run the CLI in-process with these arguments. Never raises on a bad exit code."""
    return CliRunner().invoke(main, list(args))


def copy_quickstart(destination: Path) -> Path:
    """Copy the shipped quickstart audition into *destination*; return its manifest path."""
    shutil.copytree(EXAMPLES_DIR, destination, dirs_exist_ok=True)
    return destination / "audition.yaml"


@contextmanager
def quickstart_against_stub(destination: Path) -> Iterator[Path]:
    """A writable copy of the quickstart audition, pointed at a live stub server.

    Rewriting the candidate's ``base_url`` does not touch the bar, so the copied
    lockfile still matches and the audition is FROZEN unless a test moves the bar.
    """
    manifest = copy_quickstart(destination)
    with run_stub() as base_url:
        manifest.write_text(manifest.read_text().replace(PLACEHOLDER_URL, base_url))
        yield manifest


def lower_the_bar(manifest: Path) -> None:
    """Edit the bar after the freeze — the edit the freeze mechanic exists to catch."""
    manifest.write_text(manifest.read_text().replace("min_pass_rate: 0.8", "min_pass_rate: 0.1"))


class TestRunCommand:
    """`bakeoff run` — the whole pipeline behind one command."""

    def test_frozen_run_exits_zero_and_writes_both_artefacts(self, tmp_path: Path) -> None:
        results = tmp_path / "results.json"
        report = tmp_path / "report.html"
        with quickstart_against_stub(tmp_path / "audition") as manifest:
            result = invoke(
                "run",
                str(manifest),
                "--results",
                str(results),
                "--report",
                str(report),
                "--ledger",
                str(tmp_path / "ledger.jsonl"),
            )

        assert result.exit_code == 0, result.output
        assert "bar met" in result.output
        assert "frozen" in result.output
        assert results.is_file()
        assert report.is_file()

    def test_results_json_is_a_readable_document(self, tmp_path: Path) -> None:
        results = tmp_path / "results.json"
        with quickstart_against_stub(tmp_path / "audition") as manifest:
            invoke(
                "run",
                str(manifest),
                "--results",
                str(results),
                "--report",
                str(tmp_path / "report.html"),
                "--ledger",
                str(tmp_path / "ledger.jsonl"),
            )

        document = json.loads(results.read_text())
        assert document["manifest"] == "audition.yaml"
        assert document["met_bar"] is True
        assert len(document["cases"]) == 5

    def test_run_appends_one_ledger_line(self, tmp_path: Path) -> None:
        ledger = tmp_path / "ledger.jsonl"
        with quickstart_against_stub(tmp_path / "audition") as manifest:
            for _ in range(2):
                invoke(
                    "run",
                    str(manifest),
                    "--results",
                    str(tmp_path / "results.json"),
                    "--report",
                    str(tmp_path / "report.html"),
                    "--ledger",
                    str(ledger),
                )

        lines = [line for line in ledger.read_text().splitlines() if line.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["manifest"] == "audition.yaml"

    def test_rebarred_run_is_refused_without_the_flag(self, tmp_path: Path) -> None:
        with quickstart_against_stub(tmp_path / "audition") as manifest:
            lower_the_bar(manifest)
            result = invoke("run", str(manifest))

        assert result.exit_code == CONFIG_EXIT_CODE
        assert "--rebar" in result.output

    def test_rebar_flag_runs_and_brands_the_report(self, tmp_path: Path) -> None:
        report = tmp_path / "report.html"
        with quickstart_against_stub(tmp_path / "audition") as manifest:
            lower_the_bar(manifest)
            result = invoke(
                "run",
                str(manifest),
                "--rebar",
                "--results",
                str(tmp_path / "results.json"),
                "--report",
                str(report),
                "--ledger",
                str(tmp_path / "ledger.jsonl"),
            )

        assert result.exit_code == 0, result.output
        assert "rebarred" in result.output
        assert "REBARRED" in report.read_text()

    def test_unfrozen_run_is_refused(self, tmp_path: Path) -> None:
        with quickstart_against_stub(tmp_path / "audition") as manifest:
            manifest.with_suffix(".lock").unlink()
            result = invoke("run", str(manifest))

        assert result.exit_code == CONFIG_EXIT_CODE
        assert "freeze" in result.output

    def test_missing_manifest_prints_a_message_not_a_traceback(self, tmp_path: Path) -> None:
        result = invoke("run", str(tmp_path / "nope.yaml"))

        assert result.exit_code == CONFIG_EXIT_CODE
        assert "cannot read manifest" in result.output
        assert "Traceback" not in result.output


class TestReportCommand:
    """`bakeoff report` — a re-render from results.json, never a re-run."""

    def _results_from_a_run(self, tmp_path: Path) -> Path:
        results = tmp_path / "results.json"
        with quickstart_against_stub(tmp_path / "audition") as manifest:
            invoke(
                "run",
                str(manifest),
                "--results",
                str(results),
                "--report",
                str(tmp_path / "report.html"),
                "--ledger",
                str(tmp_path / "ledger.jsonl"),
            )
        return results

    def test_rerender_matches_the_report_the_run_wrote(self, tmp_path: Path) -> None:
        results = self._results_from_a_run(tmp_path)
        again = tmp_path / "again.html"

        result = invoke("report", str(results), "--out", str(again))

        assert result.exit_code == 0, result.output
        assert again.read_text() == (tmp_path / "report.html").read_text()

    def test_rerender_contacts_no_endpoint(self, tmp_path: Path) -> None:
        """The stub is long gone by the time this renders — a re-render needs no model."""
        results = self._results_from_a_run(tmp_path)

        result = invoke("report", str(results), "--out", str(tmp_path / "offline.html"))

        assert result.exit_code == 0, result.output
        assert (tmp_path / "offline.html").is_file()

    def test_missing_results_prints_a_message(self, tmp_path: Path) -> None:
        result = invoke("report", str(tmp_path / "nope.json"))

        assert result.exit_code == CONFIG_EXIT_CODE
        assert "cannot read results" in result.output
