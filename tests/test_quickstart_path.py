"""Prove the README quickstart works from a directory that does not exist yet.

No source changes — this pins the end-to-end user journey: init → freeze → run
against the bundled stub, all starting from a fresh tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner, Result

from bakeoff.cli import main
from bakeoff.freeze import bar_hash, read_lockfile
from bakeoff.manifest import load_manifest
from bakeoff.stub import run_stub

PLACEHOLDER_URL = "http://localhost:8000"


def invoke(*args: str) -> Result:
    """Run the CLI in-process with these arguments. Never raises on a bad exit code."""
    return CliRunner().invoke(main, list(args))


class TestQuickstartPath:
    """Walk the README quickstart: init → freeze → run, from scratch."""

    def test_from_scratch(self, tmp_path: Path) -> None:
        # Step 1: bakeoff init <nonexistent-dir>
        scaffold_dir = tmp_path / "myaudition"
        assert not scaffold_dir.exists()
        result = invoke("init", str(scaffold_dir))
        assert result.exit_code == 0, result.output
        assert "audition.yaml" in result.output
        manifest = scaffold_dir / "audition.yaml"
        assert manifest.exists()
        (scaffold_dir / "suites" / "smoke").mkdir(parents=True, exist_ok=True)
        for case_file in scaffold_dir.glob("suites/smoke/*.yaml"):
            assert case_file.exists()

        # Step 2: point the manifest at the stub
        with run_stub() as base_url:
            manifest.write_text(
                manifest.read_text().replace(PLACEHOLDER_URL, base_url),
            )

            # Step 3: bakeoff freeze
            freeze_result = invoke("freeze", str(manifest))
            assert freeze_result.exit_code == 0, freeze_result.output
            lockfile = scaffold_dir / "audition.lock"
            assert lockfile.exists()

            # Step 4: bakeoff run
            results_path = tmp_path / "results.json"
            report_path = tmp_path / "report.html"
            ledger_path = tmp_path / "ledger.jsonl"
            run_result = invoke(
                "run",
                str(manifest),
                "--results",
                str(results_path),
                "--report",
                str(report_path),
                "--ledger",
                str(ledger_path),
            )
            assert run_result.exit_code == 0, run_result.output
            assert "MET" in run_result.output

            # Artifacts exist and are sensible
            assert results_path.exists()
            assert report_path.exists()
            report_text = report_path.read_text()
            assert "stub" in report_text
            results = json.loads(results_path.read_text())
            assert "pairs" in results


class TestQuickstartRebarredPath:
    """Prove the freeze story on a fresh scaffold: edit the bar, catch it,
    rebar the report. Tests only — no source changes.

    Mirrors the README's ``## The freeze mechanic`` section, run inside
    ``run_stub()`` on a directory created by ``bakeoff init``, not on the
    shipped example tree.
    """

    def test_edit_bar_catches_and_rebrands(self, tmp_path: Path) -> None:
        # Step 1: bakeoff init <nonexistent-dir>
        scaffold_dir = tmp_path / "myaudition"
        assert not scaffold_dir.exists()
        result = invoke("init", str(scaffold_dir))
        assert result.exit_code == 0, result.output

        manifest = scaffold_dir / "audition.yaml"
        assert manifest.exists()

        # Step 2: point the manifest at the stub
        with run_stub() as base_url:
            manifest.write_text(
                manifest.read_text().replace(PLACEHOLDER_URL, base_url),
            )

            # Step 3: freeze
            freeze_result = invoke("freeze", str(manifest))
            assert freeze_result.exit_code == 0, freeze_result.output
            lockfile = scaffold_dir / "audition.lock"
            assert lockfile.exists()

            # Step 4: edit the bar on disk — min_pass_rate: 0.8 → min_pass_rate: 1.0
            manifest.write_text(
                manifest.read_text().replace("min_pass_rate: 0.8", "min_pass_rate: 1.0", 1),
            )

            results_path = tmp_path / "results.json"
            report_path = tmp_path / "report.html"
            ledger_path = tmp_path / "ledger.jsonl"

            # Step 5: plain run after bar edit exits 2 and names --rebar
            run_result = invoke(
                "run",
                str(manifest),
                "--results",
                str(results_path),
                "--report",
                str(report_path),
                "--ledger",
                str(ledger_path),
            )
            assert run_result.exit_code == 2, run_result.output
            assert "--rebar" in run_result.output

            # Step 6: run with --rebar exits 0 and writes artifacts
            rebar_result = invoke(
                "run",
                str(manifest),
                "--rebar",
                "--results",
                str(results_path),
                "--report",
                str(report_path),
                "--ledger",
                str(ledger_path),
            )
            assert rebar_result.exit_code == 0, rebar_result.output
            assert results_path.exists()
            assert report_path.exists()

            # Step 7: the report contains REBARRED
            report_text = report_path.read_text()
            assert "REBARRED" in report_text

            # Step 8: the report carries two different hash strings
            assert "frozen" in report_text.lower()
            assert "current" in report_text.lower()

            # The frozen hash from the lockfile and the current hash from the
            # edited manifest must both appear in the report, and differ.
            frozen_hash = read_lockfile(lockfile).bar_hash
            current_hash = bar_hash(load_manifest(manifest).bar)
            assert frozen_hash in report_text
            assert current_hash in report_text
            assert frozen_hash != current_hash
