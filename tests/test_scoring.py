"""Scoring tests.

One test class per public name in :mod:`bakeoff.scoring`, in the order the module
declares them. New classes are appended below; mirror :class:`TestPercentile` for the
shape (a class per function, one plain assertion per behaviour).
"""

from __future__ import annotations

import pytest

from bakeoff.runner import CaseOutcome
from bakeoff.scoring import percentile, summarize


def outcome(
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
    """A CaseOutcome with everything defaulted, so a test names only what it varies."""
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


class TestPercentile:
    def test_p95_of_a_single_value_is_that_value(self) -> None:
        assert percentile([42.0], 0.95) == 42.0

    def test_p95_picks_the_worst_of_twenty(self) -> None:
        assert percentile([float(n) for n in range(1, 21)], 0.95) == 19.0

    def test_the_result_is_always_a_measured_value(self) -> None:
        values = [1.0, 2.0, 100.0]
        assert percentile(values, 0.5) in values

    def test_order_does_not_matter(self) -> None:
        assert percentile([9.0, 1.0, 5.0], 0.5) == percentile([1.0, 5.0, 9.0], 0.5)

    def test_an_empty_sequence_scores_zero(self) -> None:
        assert percentile([], 0.95) == 0.0

    def test_a_fraction_outside_the_unit_interval_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be between"):
            percentile([1.0], 1.5)


class TestSummarize:
    def test_two_candidates_on_one_suite_give_two_summaries_in_first_seen_order(self) -> None:
        outcomes = [
            outcome(candidate="alpha"),
            outcome(candidate="beta"),
        ]
        result = summarize(outcomes)
        assert len(result) == 2
        assert result[0].candidate == "alpha"
        assert result[1].candidate == "beta"

    def test_three_of_four_passes_yields_pass_rate_0_75(self) -> None:
        outcomes = [
            outcome(case_id="c1"),
            outcome(case_id="c2", passed=False),
            outcome(case_id="c3"),
            outcome(case_id="c4"),
        ]
        result = summarize(outcomes)
        assert len(result) == 1
        summary = result[0]
        assert summary.passed == 3
        assert summary.cases == 4
        assert summary.pass_rate == 0.75

    def test_errored_outcome_counts_in_errors_and_cases(self) -> None:
        outcomes = [
            outcome(case_id="c1", passed=False, error="timeout"),
            outcome(case_id="c2"),
        ]
        result = summarize(outcomes)
        summary = result[0]
        assert summary.errors == 1
        assert summary.cases == 2
        assert summary.pass_rate == 0.5

    def test_p95_latency_ms_reuses_percentile(self) -> None:
        outcomes = [outcome(case_id=f"c{n}", latency_ms=float(n * 10)) for n in range(1, 21)]
        result = summarize(outcomes)
        summary = result[0]
        assert summary.p95_latency_ms == percentile([float(n * 10) for n in range(1, 21)], 0.95)

    def test_max_tokens_per_case_is_the_largest_total(self) -> None:
        outcomes = [
            outcome(case_id="c1", prompt_tokens=3, completion_tokens=1),
            outcome(case_id="c2", prompt_tokens=10, completion_tokens=5),
            outcome(case_id="c3", prompt_tokens=2, completion_tokens=1),
        ]
        result = summarize(outcomes)
        assert result[0].max_tokens_per_case == 15
