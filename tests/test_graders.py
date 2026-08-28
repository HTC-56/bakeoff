"""Grader tests. One class per grader; mirror :class:`TestGradeExact` when adding one."""

from __future__ import annotations

from bakeoff.graders import GradeResult, grade_exact


class TestGradeExact:
    def test_identical_strings_pass_with_score_one(self) -> None:
        result = grade_exact("4", "4")
        assert result.passed is True
        assert result.score == 1.0

    def test_surrounding_whitespace_is_ignored_by_default(self) -> None:
        assert grade_exact("  4\n", "4").passed is True

    def test_whitespace_matters_when_strip_is_off(self) -> None:
        assert grade_exact("  4\n", "4", strip=False).passed is False

    def test_a_mismatch_fails_with_score_zero_and_shows_both_sides(self) -> None:
        result = grade_exact("five", "4")
        assert result.passed is False
        assert result.score == 0.0
        assert "'4'" in result.detail
        assert "'five'" in result.detail

    def test_result_is_frozen(self) -> None:
        result: GradeResult = grade_exact("4", "4")
        assert isinstance(result, GradeResult)
