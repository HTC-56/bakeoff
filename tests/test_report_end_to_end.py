"""End-to-end report tests: run the full pipeline against the bundled stub.

Load the quickstart audition, point its first candidate at the stub, exercise the
runner → scorer → judge → freeze-check → report-document → write cycle, then assert
on both artefacts.

No network calls are made — the stub binds to a random localhost port.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from bakeoff.freeze import check_freeze, find_lockfile
from bakeoff.manifest import load_audition
from bakeoff.report import (
    read_results,
    render_report,
    results_document,
    write_report,
    write_results,
)
from bakeoff.runner import run_audition
from bakeoff.scoring import judge, summarize
from bakeoff.stub import run_stub

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples" / "quickstart"
AUDITION_PATH = EXAMPLES_DIR / "audition.yaml"


class TestReportEndToEnd:
    """Run the full pipeline end-to-end and assert on results + report."""

    def _run_pipeline(self, tmp_path: Path) -> dict[str, Any]:
        """Run the quickstart audition against the stub and write artefacts.

        Returns the document dict that was written to *tmp_path*.
        """
        with run_stub() as base_url:
            audition = load_audition(AUDITION_PATH)
            audition.manifest.candidates[0].base_url = base_url
            results = asyncio.run(run_audition(audition))

        verdicts = judge(summarize(results.outcomes), audition.manifest.bar)
        freeze = check_freeze(audition.manifest.bar, find_lockfile(AUDITION_PATH))
        document = results_document(
            results,
            verdicts,
            manifest="audition.yaml",
            freeze=freeze,
            generated_at="2026-01-01T00:00:02+00:00",
        )

        write_results(tmp_path / "results.json", document)
        write_report(tmp_path / "report.html", document)
        return document

    def test_document_has_five_cases_one_pair_met_bar_true(self) -> None:
        """The document reflects a clean pass across all five smoke cases."""
        document = self._run_pipeline(Path("/tmp"))

        assert len(document["cases"]) == 5
        assert len(document["pairs"]) == 1
        assert document["met_bar"] is True
        assert document["exit_code"] == 0

    def test_read_results_equals_written_document(self) -> None:
        """read_results round-trips the file back to the original document."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            document = self._run_pipeline(tmp_path)
            round_tripped = read_results(tmp_path / "results.json")
            assert round_tripped == document

    def test_freeze_status_is_frozen(self) -> None:
        """The shipped lockfile still matches the shipped bar."""
        document = self._run_pipeline(Path("/tmp"))

        assert document["freeze"]["status"] == "frozen"

    def test_report_html_names_candidate_suite_and_case_ids(self) -> None:
        """The report page mentions stub, smoke, and every case id."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            self._run_pipeline(tmp_path)
            html = (tmp_path / "report.html").read_text()

            assert "stub" in html
            assert "smoke" in html
            for case_id in ("01-exact", "02-contains", "03-regex", "04-numeric", "05-json-schema"):
                assert case_id in html

    def test_page_contains_frozen_not_rebarred(self) -> None:
        """FROZEN banner is present; REBARRED is not."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            self._run_pipeline(tmp_path)
            html = (tmp_path / "report.html").read_text()

            assert "FROZEN" in html
            assert "REBARRED" not in html

    def test_rerender_equals_written_report(self) -> None:
        """Re-rendering from the file on disk produces identical HTML."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            self._run_pipeline(tmp_path)
            written = (tmp_path / "report.html").read_text()
            document = read_results(tmp_path / "results.json")
            rerendered = render_report(document)
            assert rerendered == written
