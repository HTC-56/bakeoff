"""Report tests: the results document, its file, and the HTML render.

One test class per public name in :mod:`bakeoff.report`, in the order the module
declares them. New classes are appended below; mirror :class:`TestRenderReport` for
the shape (a class per function, one plain assertion per behaviour).

The helpers at the top build a whole results document from defaults, so a test names
only the field it varies. ``GENERATED_AT`` is passed everywhere a document is built,
because a render must be reproducible byte for byte.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bakeoff.freeze import (
    FreezeCheck,
    FreezeStatus,
    check_freeze,
    freeze_bar,
    lockfile_path,
    read_lockfile,
    write_lockfile,
)
from bakeoff.manifest import Thresholds, load_manifest
from bakeoff.report import (
    REPORT_VERSION,
    ReportError,
    _ms,
    read_results,
    render_report,
    results_document,
    write_report,
    write_results,
)
from bakeoff.runner import CaseOutcome, RunResults
from bakeoff.scoring import PairSummary, PairVerdict, percentile

# --- helpers ----------------------------------------------------------------

GENERATED_AT = "2026-01-01T00:00:02+00:00"
STARTED_AT = "2026-01-01T00:00:00+00:00"
FINISHED_AT = "2026-01-01T00:00:01+00:00"

FROZEN_HASH = "sha256:" + "a" * 64
CURRENT_HASH = "sha256:" + "b" * 64


def make_outcome(
    *,
    suite: str = "smoke",
    candidate: str = "stub",
    case_id: str = "c1",
    prompt: str = "echo: 4",
    completion: str = "4",
    passed: bool = True,
    latency_ms: float = 12.0,
    prompt_tokens: int = 3,
    completion_tokens: int = 1,
    error: str | None = None,
) -> CaseOutcome:
    """A CaseOutcome with everything defaulted."""
    return CaseOutcome(
        candidate=candidate,
        suite=suite,
        case_id=case_id,
        prompt=prompt,
        completion="" if error else completion,
        passed=passed,
        score=1.0 if passed else 0.0,
        detail="exact match" if passed else "mismatch",
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        attempts=1,
        error=error,
        finish_reason="" if error else "stop",
    )


def make_results(outcomes: list[CaseOutcome] | None = None) -> RunResults:
    """A RunResults with fixed timestamps."""
    return RunResults(
        outcomes=tuple(outcomes if outcomes is not None else [make_outcome()]),
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
    )


def make_verdict(
    *,
    suite: str = "smoke",
    candidate: str = "stub",
    cases: int = 1,
    passed: int = 1,
    errors: int = 0,
    p95_latency_ms: float = 12.0,
    max_tokens_per_case: int = 4,
    met: bool = True,
    reasons: tuple[str, ...] = (),
) -> PairVerdict:
    """A PairVerdict with a permissive default bar."""
    summary = PairSummary(
        suite=suite,
        candidate=candidate,
        cases=cases,
        passed=passed,
        errors=errors,
        pass_rate=passed / cases if cases else 0.0,
        p95_latency_ms=p95_latency_ms,
        max_tokens_per_case=max_tokens_per_case,
    )
    thresholds = Thresholds(
        min_pass_rate=1.0,
        max_p95_latency_ms=2000.0,
        max_tokens_per_case=200,
    )
    return PairVerdict(summary=summary, thresholds=thresholds, met=met, reasons=reasons)


def make_freeze(status: FreezeStatus = FreezeStatus.FROZEN) -> FreezeCheck:
    """A FreezeCheck in any of the three states, with stable fake hashes."""
    if status is FreezeStatus.UNFROZEN:
        return FreezeCheck(status=status, current_hash=CURRENT_HASH, frozen_hash=None)
    if status is FreezeStatus.FROZEN:
        return FreezeCheck(status=status, current_hash=FROZEN_HASH, frozen_hash=FROZEN_HASH)
    return FreezeCheck(status=status, current_hash=CURRENT_HASH, frozen_hash=FROZEN_HASH)


def make_document(
    *,
    outcomes: list[CaseOutcome] | None = None,
    verdicts: list[PairVerdict] | None = None,
    manifest: str = "audition.yaml",
    freeze: FreezeCheck | None = None,
) -> dict[str, Any]:
    """A whole results document, built the way the CLI will build it."""
    return results_document(
        make_results(outcomes),
        verdicts if verdicts is not None else [make_verdict()],
        manifest=manifest,
        freeze=freeze,
        generated_at=GENERATED_AT,
    )


# --- tests ------------------------------------------------------------------


class TestResultsDocument:
    def test_carries_version_and_injected_timestamp(self) -> None:
        document = make_document()
        assert document["version"] == REPORT_VERSION
        assert document["generated_at"] == GENERATED_AT

    def test_manifest_and_run_window_are_recorded(self) -> None:
        document = make_document(manifest="audition.yaml")
        assert document["manifest"] == "audition.yaml"
        assert document["started_at"] == STARTED_AT
        assert document["finished_at"] == FINISHED_AT

    def test_met_bar_and_exit_code_agree_with_the_verdicts(self) -> None:
        met = make_document()
        missed = make_document(verdicts=[make_verdict(met=False, reasons=("pass rate low",))])
        assert (met["met_bar"], met["exit_code"]) == (True, 0)
        assert (missed["met_bar"], missed["exit_code"]) == (False, 1)

    def test_pair_entry_carries_thresholds_and_reasons(self) -> None:
        document = make_document(verdicts=[make_verdict(met=False, reasons=("too slow",))])
        pair = document["pairs"][0]
        assert pair["thresholds"]["min_pass_rate"] == 1.0
        assert pair["reasons"] == ["too slow"]
        assert pair["suite"] == "smoke"

    def test_case_entry_carries_the_derived_fields(self) -> None:
        document = make_document(outcomes=[make_outcome(prompt_tokens=5, completion_tokens=2)])
        case = document["cases"][0]
        assert case["total_tokens"] == 7
        assert case["errored"] is False
        assert case["completion"] == "4"

    def test_freeze_is_none_when_no_check_was_made(self) -> None:
        assert make_document()["freeze"] is None

    def test_freeze_records_status_and_both_hashes(self) -> None:
        document = make_document(freeze=make_freeze(FreezeStatus.REBARRED))
        assert document["freeze"] == {
            "status": "rebarred",
            "bar_hash": CURRENT_HASH,
            "frozen_hash": FROZEN_HASH,
        }

    def test_whole_document_survives_json_dumps(self) -> None:
        document = make_document(freeze=make_freeze())
        assert json.loads(json.dumps(document)) == document


class TestWriteAndReadResults:
    def test_round_trip_is_unchanged(self, tmp_path: Path) -> None:
        document = make_document(freeze=make_freeze())
        path = tmp_path / "out" / "results.json"
        write_results(path, document)
        assert read_results(path) == document

    def test_file_is_indented_and_newline_terminated(self, tmp_path: Path) -> None:
        path = tmp_path / "results.json"
        write_results(path, make_document())
        text = path.read_text()
        assert text.endswith("}\n")
        assert '\n  "cases": [' in text

    def test_missing_file_raises_report_error(self, tmp_path: Path) -> None:
        with pytest.raises(ReportError, match="cannot read results"):
            read_results(tmp_path / "nope.json")

    def test_invalid_json_raises_report_error(self, tmp_path: Path) -> None:
        path = tmp_path / "results.json"
        path.write_text("{not json")
        with pytest.raises(ReportError, match="not valid JSON"):
            read_results(path)

    def test_json_that_is_not_an_object_raises_report_error(self, tmp_path: Path) -> None:
        path = tmp_path / "results.json"
        path.write_text("[1, 2, 3]")
        with pytest.raises(ReportError, match="must be a JSON object"):
            read_results(path)

    def test_unknown_version_raises_report_error(self, tmp_path: Path) -> None:
        path = tmp_path / "results.json"
        document = make_document()
        document["version"] = 99
        write_results(path, document)
        with pytest.raises(ReportError, match="unsupported results version"):
            read_results(path)


class TestRenderReport:
    def test_is_a_whole_html_document(self) -> None:
        html = render_report(make_document())
        assert html.startswith("<!doctype html>")
        assert html.rstrip().endswith("</html>")

    def test_title_names_the_manifest(self) -> None:
        html = render_report(make_document(manifest="audition.yaml"))
        assert "audition.yaml</title>" in html

    def test_headline_reports_the_verdict(self) -> None:
        assert "BAR MET" in render_report(make_document())
        missed = render_report(make_document(verdicts=[make_verdict(met=False)]))
        assert "BAR MISSED" in missed

    def test_scoreboard_names_every_pair(self) -> None:
        html = render_report(
            make_document(
                verdicts=[
                    make_verdict(candidate="stub"),
                    make_verdict(candidate="other", met=False, reasons=("pass rate low",)),
                ]
            )
        )
        assert "<td>stub</td>" in html
        assert "<td>other</td>" in html
        assert "pass rate low" in html

    def test_measurements_are_shown_beside_their_bar(self) -> None:
        html = render_report(make_document())
        assert "100%" in html
        assert "&ge; 100%" in html
        assert "&le; 2000 ms" in html

    def test_values_from_the_document_are_escaped(self) -> None:
        html = render_report(make_document(manifest="<script>evil</script>.yaml"))
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestFreezeBanner:
    def test_frozen_run_says_frozen(self) -> None:
        html = render_report(make_document(freeze=make_freeze(FreezeStatus.FROZEN)))
        assert "FROZEN" in html
        assert FROZEN_HASH in html

    def test_rebarred_run_is_branded_with_both_hashes(self) -> None:
        html = render_report(make_document(freeze=make_freeze(FreezeStatus.REBARRED)))
        assert "REBARRED" in html
        assert FROZEN_HASH in html
        assert CURRENT_HASH in html

    def test_unfrozen_run_says_no_bar_was_pre_registered(self) -> None:
        html = render_report(make_document(freeze=make_freeze(FreezeStatus.UNFROZEN)))
        assert "UNFROZEN" in html

    def test_missing_check_says_the_freeze_was_not_recorded(self) -> None:
        assert "FREEZE NOT RECORDED" in render_report(make_document())


class TestWriteReport:
    def test_writes_the_rendered_page_to_disk(self, tmp_path: Path) -> None:
        document = make_document()
        path = tmp_path / "out" / "report.html"
        write_report(path, document)
        assert path.read_text() == render_report(document)


class TestCaseDrilldown:
    def test_details_block_names_suite_and_candidate(self) -> None:
        html = render_report(make_document())
        assert "<details>" in html
        assert "smoke / stub" in html

    def test_every_case_id_appears_in_the_page(self) -> None:
        outcomes = [
            make_outcome(case_id="alpha", completion="1"),
            make_outcome(case_id="beta", completion="2"),
        ]
        html = render_report(make_document(outcomes=outcomes))
        assert "alpha" in html
        assert "beta" in html

    def test_completion_text_appears_in_the_page(self) -> None:
        html = render_report(make_document(outcomes=[make_outcome(completion="hello world")]))
        assert "hello world" in html

    def test_html_in_completion_is_escaped(self) -> None:
        html = render_report(make_document(outcomes=[make_outcome(completion="<b>hi</b>")]))
        assert "&lt;b&gt;" in html
        assert "<b>hi</b>" not in html

    def test_error_case_shows_error_text_and_case_fail(self) -> None:
        outcome = make_outcome(error="boom")
        html = render_report(make_document(outcomes=[outcome]))
        assert "boom" in html
        assert "case-fail" in html


class TestSpend:
    def test_two_candidates_render_two_rows(self) -> None:
        outcomes = [
            make_outcome(candidate="alpha", case_id="a1"),
            make_outcome(candidate="beta", case_id="b1"),
        ]
        html = render_report(make_document(outcomes=outcomes))
        assert "<td>alpha</td>" in html
        assert "<td>beta</td>" in html

    def test_total_tokens_cell_equals_hand_sum(self) -> None:
        outcomes = [
            make_outcome(case_id="a1", prompt_tokens=3, completion_tokens=1),
            make_outcome(case_id="a2", prompt_tokens=5, completion_tokens=2),
        ]
        document = make_document(outcomes=outcomes)
        html = render_report(document)
        total = sum(c["total_tokens"] for c in document["cases"])
        assert f"<td>{total}</td>" in html

    def test_p95_cell_matches_percentile(self) -> None:
        outcomes = [
            make_outcome(case_id="a1", latency_ms=10.0),
            make_outcome(case_id="a2", latency_ms=20.0),
            make_outcome(case_id="a3", latency_ms=30.0),
        ]
        document = make_document(outcomes=outcomes)
        html = render_report(document)
        latencies = [float(c["latency_ms"]) for c in document["cases"]]
        expected_p95 = percentile(latencies, 0.95)
        assert f"<td>{_ms(expected_p95)}</td>" in html

    def test_empty_document_renders_muted_note(self) -> None:
        document = make_document(outcomes=[], verdicts=[])
        html = render_report(document)
        assert "No cases were run" in html

    def test_spend_does_not_replace_scoreboard(self) -> None:
        document = make_document()
        html = render_report(document)
        assert "Scoreboard" in html
        assert "Spend" in html


class TestRebarredReport:
    """Prove REBARRED branding from a manifest frozen then edited on disk.

    Tests only — no source changes. Mirrors ``TestRebarredEndToEnd`` in
    ``tests/test_freeze.py``, but asserts on the rendered report page, not
    the freeze check.
    """

    def test_rebarred_report(self, tmp_path: Path) -> None:
        # Copy the example manifest text onto tmp_path.
        example_manifest = (
            Path(__file__).resolve().parent.parent / "examples" / "quickstart" / "audition.yaml"
        )
        manifest_path = tmp_path / "audition.yaml"
        manifest_path.write_text(example_manifest.read_text())

        # Load, freeze, and write the lockfile.
        manifest = load_manifest(manifest_path)
        lock = freeze_bar(manifest, manifest_path=manifest_path)
        lock_path = lockfile_path(manifest_path)
        write_lockfile(lock_path, lock)

        # 1. Report of the frozen manifest contains FROZEN, not REBARRED.
        frozen_check = check_freeze(manifest.bar, read_lockfile(lock_path))
        frozen_doc = make_document(freeze=frozen_check)
        frozen_html = render_report(frozen_doc)
        assert "FROZEN" in frozen_html
        assert "REBARRED" not in frozen_html

        # 2. Lower the bar: rewrite min_pass_rate: 0.8 → min_pass_rate: 0.5.
        edited = manifest_path.read_text().replace("min_pass_rate: 0.8", "min_pass_rate: 0.5", 1)
        manifest_path.write_text(edited)
        edited_manifest = load_manifest(manifest_path)

        rebarred_check = check_freeze(edited_manifest.bar, read_lockfile(lock_path))
        assert rebarred_check.status == FreezeStatus.REBARRED

        # 3. Report of the rebarred manifest contains REBARRED.
        rebarred_doc = make_document(freeze=rebarred_check)
        rebarred_html = render_report(rebarred_doc)
        assert "REBARRED" in rebarred_html

        # 4. Contains both the lockfile's bar_hash and the current check's current_hash,
        #    and those two strings differ.
        lock = read_lockfile(lock_path)
        assert lock.bar_hash in rebarred_html
        assert rebarred_check.current_hash in rebarred_html
        assert lock.bar_hash != rebarred_check.current_hash

        # 5. It also names --rebar, so a reader learns how the run was allowed.
        assert "--rebar" in rebarred_html

        # 6. Rendering the same rebarred document twice gives identical strings.
        assert render_report(rebarred_doc) == render_report(rebarred_doc)


class TestSelfContained:
    """Assert the report is one self-contained file: no <script>, <link>,

    @import, url( or external URL, and a re-render never changes it.
    """

    def test_no_external_references_in_rendered_page(self) -> None:
        document = make_document()
        html = render_report(document)
        assert "http://" not in html
        assert "https://" not in html
        assert "<script" not in html
        assert "<link" not in html
        assert "@import" not in html
        assert "url(" not in html

    def test_exactly_one_style_block(self) -> None:
        document = make_document()
        html = render_report(document)
        assert html.count("<style>") == 1

    def test_re_render_is_identical(self) -> None:
        document = make_document()
        first = render_report(document)
        second = render_report(document)
        assert first == second

    def test_write_read_re_render_is_identical(self, tmp_path: Path) -> None:
        document = make_document()
        original = render_report(document)

        # Write results and read back, then render the re-read document.
        results_path = tmp_path / "results.json"
        write_results(results_path, document)
        re_read = read_results(results_path)
        re_rendered = render_report(re_read)

        assert re_rendered == original

    def test_url_in_completion_escapes_without_link(self) -> None:
        outcome = make_outcome(completion="see http://example.com/x")
        document = make_document(outcomes=[outcome])
        html = render_report(document)
        assert "<a " not in html
        assert "http://example.com/x" in html  # escaped text is fine
