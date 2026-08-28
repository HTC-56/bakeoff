"""Quickstart example tests.

Verifies that the example audition in examples/quickstart loads, the smoke
suite has the five expected cases, and every case really does pass against the
bundled stub.

Mirror :class:`TestQuickstart` when adding a new example suite.
"""

from __future__ import annotations

from pathlib import Path

from bakeoff.freeze import FreezeStatus, check_freeze, find_lockfile
from bakeoff.manifest import load_audition
from bakeoff.stub import canned_reply
from bakeoff.suite import run_grader

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples" / "quickstart"
AUDITION_PATH = EXAMPLES_DIR / "audition.yaml"


class TestQuickstart:
    def test_load_audition_returns_one_candidate_and_one_suite(self) -> None:
        audition = load_audition(AUDITION_PATH)
        assert len(audition.manifest.candidates) == 1
        assert len(audition.suites) == 1

    def test_smoke_suite_has_five_cases_with_five_distinct_kinds(self) -> None:
        audition = load_audition(AUDITION_PATH)
        smoke = audition.suite("smoke")
        assert len(smoke) == 5
        kinds = {case.grader.kind for case in smoke.cases}
        assert kinds == {"exact", "contains", "regex", "numeric_tolerance", "json_schema"}

    def test_every_case_passes_against_the_bundled_stub(self) -> None:
        audition = load_audition(AUDITION_PATH)
        smoke = audition.suite("smoke")
        for case in smoke.cases:
            reply = canned_reply(case.prompt)
            result = run_grader(case.grader, reply)
            assert result.passed, f"case {case.id!r} failed: {result.detail}"

    def test_candidate_base_url_is_localhost(self) -> None:
        audition = load_audition(AUDITION_PATH)
        candidate = audition.manifest.candidates[0]
        assert candidate.base_url.startswith("http://localhost")


class TestQuickstartFreeze:
    """Assert the shipped lockfile exists and matches the shipped bar."""

    def test_lockfile_exists(self) -> None:
        assert find_lockfile(AUDITION_PATH) is not None

    def test_bar_matches_lockfile(self) -> None:
        lock = find_lockfile(AUDITION_PATH)
        assert lock is not None
        audition = load_audition(AUDITION_PATH)
        check = check_freeze(audition.manifest.bar, lock)
        assert check.status == FreezeStatus.FROZEN

    def test_lockfile_manifest_is_name_not_path(self) -> None:
        lock = find_lockfile(AUDITION_PATH)
        assert lock is not None
        assert lock.manifest == "audition.yaml"

    def test_lockfile_bar_hash_starts_with_sha256(self) -> None:
        lock = find_lockfile(AUDITION_PATH)
        assert lock is not None
        assert lock.bar_hash.startswith("sha256:")
