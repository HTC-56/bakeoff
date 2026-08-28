"""Scoring tests.

One test class per public name in :mod:`bakeoff.scoring`, in the order the module
declares them. New classes are appended below; mirror :class:`TestPercentile` for the
shape (a class per function, one plain assertion per behaviour).
"""

from __future__ import annotations

import pytest

from bakeoff.runner import CaseOutcome
from bakeoff.scoring import percentile


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
