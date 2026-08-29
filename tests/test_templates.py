"""Tests for :mod:`bakeoff.templates`.

Verifies that ``write_scaffold`` produces a working quickstart audition that
loads, passes against the bundled stub, and handles the force flag.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bakeoff.manifest import load_audition
from bakeoff.stub import canned_reply
from bakeoff.suite import run_grader
from bakeoff.templates import (
    TemplateError,
    write_scaffold,
)


class TestWriteScaffold:
    def test_returns_six_paths_and_all_exist(self, tmp_path: Path) -> None:
        paths = write_scaffold(tmp_path)
        assert len(paths) == 6
        for p in paths:
            assert p.exists(), f"{p} was not written"

    def test_load_audition_gives_one_candidate_and_one_suite(self, tmp_path: Path) -> None:
        write_scaffold(tmp_path)
        audition = load_audition(tmp_path / "audition.yaml")
        assert len(audition.manifest.candidates) == 1
        assert len(audition.suites) == 1

    def test_five_distinct_grader_kinds(self, tmp_path: Path) -> None:
        write_scaffold(tmp_path)
        audition = load_audition(tmp_path / "audition.yaml")
        smoke = audition.suite("smoke")
        kinds = {case.grader.kind for case in smoke.cases}
        assert kinds == {
            "exact",
            "contains",
            "regex",
            "numeric_tolerance",
            "json_schema",
        }

    def test_every_case_passes_against_the_bundled_stub(self, tmp_path: Path) -> None:
        write_scaffold(tmp_path)
        audition = load_audition(tmp_path / "audition.yaml")
        smoke = audition.suite("smoke")
        for case in smoke.cases:
            reply = canned_reply(case.prompt)
            result = run_grader(case.grader, reply)
            assert result.passed, f"case {case.id!r} failed: {result.detail}"

    def test_no_lockfile_is_written(self, tmp_path: Path) -> None:
        write_scaffold(tmp_path)
        assert not (tmp_path / "audition.lock").exists()

    def test_write_twice_raises_template_error(self, tmp_path: Path) -> None:
        write_scaffold(tmp_path)
        with pytest.raises(TemplateError, match="already exists"):
            write_scaffold(tmp_path)

    def test_force_overwrites(self, tmp_path: Path) -> None:
        write_scaffold(tmp_path)
        # second call without force raises
        with pytest.raises(TemplateError, match="already exists"):
            write_scaffold(tmp_path)
        # with force=True it succeeds
        paths = write_scaffold(tmp_path, force=True)
        assert len(paths) == 6


class TestWriteScaffoldMkdir:
    def test_deeply_nested_directory_is_created(self, tmp_path: Path) -> None:
        """write_scaffold creates a directory that does not exist yet."""
        dest = tmp_path / "a" / "b"
        assert not dest.exists()
        paths = write_scaffold(dest)
        assert len(paths) == 6
        for p in paths:
            assert p.exists(), f"{p} was not written"

    def test_two_levels_deep_nested_also_works(self, tmp_path: Path) -> None:
        """A deeper nesting level (three segments) also works."""
        dest = tmp_path / "x" / "y" / "z"
        assert not dest.exists()
        paths = write_scaffold(dest)
        assert len(paths) == 6
        for p in paths:
            assert p.exists(), f"{p} was not written"

    def test_twice_without_force_raises_naming_manifest(self, tmp_path: Path) -> None:
        """Second call without force raises; message names audition.yaml."""
        dest = tmp_path / "one"
        write_scaffold(dest)
        with pytest.raises(TemplateError, match=r"audition\.yaml.*already exists"):
            write_scaffold(dest)

    def test_twice_with_force_succeeds(self, tmp_path: Path) -> None:
        """force=True rewrites all six files on a second call."""
        dest = tmp_path / "two"
        write_scaffold(dest)
        paths = write_scaffold(dest, force=True)
        assert len(paths) == 6
        for p in paths:
            assert p.exists(), f"{p} was not written"
