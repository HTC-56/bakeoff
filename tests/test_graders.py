"""Grader tests. One class per grader; mirror :class:`TestGradeExact` when adding one."""

from __future__ import annotations

import pytest

from bakeoff.graders import (
    GraderConfigError,
    GradeResult,
    grade_contains,
    grade_exact,
    grade_numeric_tolerance,
    grade_regex,
)


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


class TestGradeContains:
    def test_substring_in_middle_passes_with_score_one(self) -> None:
        result = grade_contains("the answer is 42", "42")
        assert result.passed is True
        assert result.score == 1.0

    def test_absent_substring_fails_with_score_zero(self) -> None:
        result = grade_contains("the answer is 42", "99")
        assert result.passed is False
        assert result.score == 0.0

    def test_case_difference_fails_when_case_sensitive(self) -> None:
        result = grade_contains("hello", "HELLO")
        assert result.passed is False

    def test_case_difference_passes_when_case_insensitive(self) -> None:
        result = grade_contains("hello", "HELLO", case_sensitive=False)
        assert result.passed is True

    def test_failure_detail_mentions_missing_substring(self) -> None:
        result = grade_contains("the answer is 42", "missing")
        assert "missing" in result.detail


class TestGradeRegex:
    def test_pattern_matching_part_of_completion_passes(self) -> None:
        result = grade_regex("the answer is 42", r"\d+")
        assert result.passed is True
        assert result.score == 1.0

    def test_pattern_matching_nothing_fails_with_score_zero(self) -> None:
        result = grade_regex("the answer is 42", r"\d+")
        assert result.passed is True
        result2 = grade_regex("no digits here", r"\d+")
        assert result2.passed is False
        assert result2.score == 0.0

    def test_partial_pattern_fails_when_fullmatch_true(self) -> None:
        result = grade_regex("hello", r"hel", fullmatch=True)
        assert result.passed is False
        assert result.score == 0.0

    def test_partial_pattern_passes_by_default(self) -> None:
        result = grade_regex("hello", r"hel")
        assert result.passed is True

    def test_uncompilable_pattern_raises_grader_config_error(self) -> None:
        with pytest.raises(
            GraderConfigError,
            match=r"pattern '\('\s*is not a valid regex",
        ):
            grade_regex("anything", "(")

    def test_raised_message_contains_offending_pattern(self) -> None:
        try:
            grade_regex("anything", "[bad")
            raise AssertionError("GraderConfigError not raised")
        except GraderConfigError as exc:
            assert "[bad" in str(exc)


class TestGradeNumericTolerance:
    def test_exact_numeric_match_passes_with_default_tolerance(self) -> None:
        result = grade_numeric_tolerance("3.14", 3.14)
        assert result.passed is True
        assert result.score == 1.0

    def test_value_inside_tolerance_passes(self) -> None:
        result = grade_numeric_tolerance("3.14", 3.1, tolerance=0.05)
        assert result.passed is True
        assert result.score == 1.0

    def test_value_outside_tolerance_fails_with_score_zero(self) -> None:
        result = grade_numeric_tolerance("5.0", 3.1, tolerance=0.05)
        assert result.passed is False
        assert result.score == 0.0

    def test_value_at_tolerance_edge_passes(self) -> None:
        result = grade_numeric_tolerance("3.15", 3.1, tolerance=0.05)
        assert result.passed is True
        assert result.score == 1.0

    def test_non_numeric_completion_fails_rather_than_raise(self) -> None:
        result = grade_numeric_tolerance("about four", 4.0)
        assert result.passed is False
        assert result.score == 0.0
        assert "not numeric" in result.detail

    def test_negative_tolerance_raises_grader_config_error(self) -> None:
        with pytest.raises(GraderConfigError):
            grade_numeric_tolerance("4.0", 4.0, tolerance=-0.1)
