"""Ledger tests.

One test class per public name in :mod:`bakeoff.ledger`, in the order the module
declares them. New classes are appended below; mirror :class:`TestPercentile` for
the shape (a class per function, one plain assertion per behaviour).
"""

from __future__ import annotations

import json
from pathlib import Path

from bakeoff.freeze import FreezeCheck, FreezeStatus
from bakeoff.ledger import append_run, read_ledger, run_record
from bakeoff.manifest import Thresholds
from bakeoff.runner import CaseOutcome, RunResults
from bakeoff.scoring import PairSummary, PairVerdict

# --- helpers ----------------------------------------------------------------


def _outcome(
    *,
    suite: str = "smoke",
    candidate: str = "cand",
    case_id: str = "c1",
    passed: bool = True,
    latency_ms: float = 10.0,
    prompt_tokens: int = 3,
    completion_tokens: int = 1,
    error: str | None = None,
) -> CaseOutcome:
    """A CaseOutcome with everything defaulted."""
    return CaseOutcome(
        candidate=candidate,
        suite=suite,
        case_id=case_id,
        prompt="echo: 4",
        completion="" if error else "4",
        passed=passed,
        score=1.0 if passed else 0.0,
        detail="exact match" if passed else "mismatch",
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        attempts=1,
        error=error,
    )


def _run_results(*, outcomes: list[CaseOutcome] | None = None) -> RunResults:
    """A RunResults with timestamps that survive JSON round-trips."""
    started = "2026-01-01T00:00:00+00:00"
    finished = "2026-01-01T00:00:01+00:00"
    return RunResults(
        outcomes=tuple(outcomes or [_outcome()]),
        started_at=started,
        finished_at=finished,
    )


def _verdict(
    *,
    suite: str = "smoke",
    candidate: str = "cand",
    cases: int = 1,
    passed: int = 1,
    errors: int = 0,
    met: bool = True,
) -> PairVerdict:
    """A PairVerdict with a permissive default bar."""
    summary = PairSummary(
        suite=suite,
        candidate=candidate,
        cases=cases,
        passed=passed,
        errors=errors,
        pass_rate=passed / cases if cases else 0.0,
        p95_latency_ms=10.0,
        max_tokens_per_case=4,
    )
    thresholds = Thresholds(
        min_pass_rate=0.5,
        max_p95_latency_ms=1000.0,
        max_tokens_per_case=100,
    )
    return PairVerdict(
        summary=summary,
        thresholds=thresholds,
        met=met,
        reasons=(),
    )


# --- tests ------------------------------------------------------------------


class TestAppendRun:
    def test_append_run_writes_one_line_and_read_ledger_returns_it(self, tmp_path: Path) -> None:
        path = tmp_path / "ledger.jsonl"
        record = {"hello": "world"}
        append_run(path, record)
        records = read_ledger(path)
        assert len(records) == 1
        assert records[0] == record

    def test_appending_twice_gives_two_records_in_order(self, tmp_path: Path) -> None:
        path = tmp_path / "ledger.jsonl"
        append_run(path, {"n": 1})
        append_run(path, {"n": 2})
        records = read_ledger(path)
        assert len(records) == 2
        assert records[0]["n"] == 1
        assert records[1]["n"] == 2


class TestReadLedger:
    def test_nonexistent_path_returns_empty_list(self) -> None:
        assert read_ledger("/no/such/path/ledger.jsonl") == []


class TestRunRecord:
    def test_met_bar_false_when_any_verdict_not_met(self) -> None:
        results = _run_results()
        verdicts = [_verdict(met=False), _verdict(met=True)]
        record = run_record(results, verdicts, manifest="test.yaml")
        assert record["met_bar"] is False

    def test_met_bar_true_when_all_met(self) -> None:
        results = _run_results()
        verdicts = [_verdict(met=True), _verdict(met=True)]
        record = run_record(results, verdicts, manifest="test.yaml")
        assert record["met_bar"] is True

    def test_json_dumps_does_not_raise(self) -> None:
        results = _run_results()
        verdicts = [_verdict(met=False)]
        record = run_record(results, verdicts, manifest="test.yaml")
        # Must not raise — every value is JSON-safe
        json.dumps(record, sort_keys=True)


class TestRunRecordFreeze:
    def test_no_freeze_argument_gives_none(self) -> None:
        results = _run_results()
        verdicts = [_verdict()]
        record = run_record(results, verdicts, manifest="test.yaml")
        assert record["freeze"] is None
        # Other keys still present
        assert "started_at" in record
        assert "manifest" in record
        assert "cases" in record
        assert "met_bar" in record
        assert "pairs" in record

    def test_frozen_check_records_status_and_bar_hash(self) -> None:
        results = _run_results()
        verdicts = [_verdict()]
        check = FreezeCheck(
            status=FreezeStatus.FROZEN,
            current_hash="abc123",
            frozen_hash="abc123",
        )
        record = run_record(results, verdicts, manifest="test.yaml", freeze=check)
        assert record["freeze"]["status"] == "frozen"
        assert record["freeze"]["bar_hash"] == "abc123"
        assert record["freeze"]["frozen_hash"] == "abc123"

    def test_rebarred_check_records_two_different_hashes(self) -> None:
        results = _run_results()
        verdicts = [_verdict()]
        check = FreezeCheck(
            status=FreezeStatus.REBARRED,
            current_hash="current",
            frozen_hash="frozen",
        )
        record = run_record(results, verdicts, manifest="test.yaml", freeze=check)
        assert record["freeze"]["status"] == "rebarred"
        assert record["freeze"]["bar_hash"] == "current"
        assert record["freeze"]["frozen_hash"] == "frozen"

    def test_record_survives_json_dumps(self) -> None:
        results = _run_results()
        verdicts = [_verdict()]
        check = FreezeCheck(
            status=FreezeStatus.FROZEN,
            current_hash="abc",
            frozen_hash="abc",
        )
        record = run_record(results, verdicts, manifest="test.yaml", freeze=check)
        # Must not raise — enum .value is a str, not the enum itself
        json.dumps(record, sort_keys=True)
