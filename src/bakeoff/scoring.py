"""Scoring: turn a pile of case outcomes into a verdict against the pre-registered bar.

The runner (:mod:`bakeoff.runner`) records one :class:`~bakeoff.runner.CaseOutcome`
per case; the report renders. In between, this module answers the only question the
audition was set up to ask: *did this candidate clear the bar on this suite?*

Everything here is pure — no I/O, no clock, no network — so the scoreboard on the
report is reproducible from ``results.json`` alone, which is what makes
``bakeoff report`` a re-render rather than a re-run.

The pipeline is two steps, one per aggregate:

* :class:`PairSummary` — the measured numbers for one suite x candidate pair.
* :class:`PairVerdict` — that summary held against the :class:`~bakeoff.manifest.Thresholds`
  the manifest's bar gives the same pair, plus a plain-language reason per breach.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .manifest import Bar, Thresholds
from .runner import CaseOutcome


def percentile(values: Sequence[float], fraction: float) -> float:
    """The nearest-rank percentile of ``values`` — ``percentile(xs, 0.95)`` is p95.

    Nearest rank (not interpolated) is chosen on purpose: every value it returns is a
    latency the audition actually measured, so a number on the report can be traced
    to a case in the drill-down. An empty sequence scores 0.0, which keeps a pair
    that returned nothing from inventing a latency.
    """
    if not 0.0 <= fraction <= 1.0:
        raise ValueError(f"fraction must be between 0.0 and 1.0, got {fraction}")
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


@dataclass(frozen=True)
class PairSummary:
    """What one candidate measured on one suite. The three bar dimensions plus counts.

    ``errors`` counts outcomes the endpoint never usably answered; they are included
    in ``cases`` and count against ``pass_rate``, because an audition that cannot
    reach a model has not met the bar.
    """

    suite: str
    candidate: str
    cases: int
    passed: int
    errors: int
    pass_rate: float
    p95_latency_ms: float
    max_tokens_per_case: int


@dataclass(frozen=True)
class PairVerdict:
    """One :class:`PairSummary` judged against the bar that was registered for it.

    ``reasons`` is empty when ``met`` is true and otherwise holds one line per
    breached threshold, naming the measurement and the bar it missed — the text the
    report prints under a red row.
    """

    summary: PairSummary
    thresholds: Thresholds
    met: bool
    reasons: tuple[str, ...]


def summarize(outcomes: Sequence[CaseOutcome]) -> tuple[PairSummary, ...]:
    """One :class:`PairSummary` per ``(suite, candidate)`` group, first-seen order.

    Groups the flat list of :class:`~bakeoff.runner.CaseOutcome` records by the pair
    of suite name and candidate name, then builds one row per pair.  An outcome that
    both passed *and* errored is counted in both ``passed`` and ``errors`` — the
    grader never does that, but the math is safe either way.
    """
    groups: dict[tuple[str, str], list[CaseOutcome]] = {}
    order: list[tuple[str, str]] = []
    for o in outcomes:
        key = (o.suite, o.candidate)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(o)

    summaries: list[PairSummary] = []
    for suite, candidate in order:
        cases = groups[(suite, candidate)]
        n = len(cases)
        passed = sum(1 for c in cases if c.passed)
        errors = sum(1 for c in cases if c.errored)
        summaries.append(
            PairSummary(
                suite=suite,
                candidate=candidate,
                cases=n,
                passed=passed,
                errors=errors,
                pass_rate=passed / n if n else 0.0,
                p95_latency_ms=percentile([c.latency_ms for c in cases], 0.95),
                max_tokens_per_case=max((c.total_tokens for c in cases), default=0),
            )
        )
    return tuple(summaries)


def judge(summaries: Sequence[PairSummary], bar: Bar) -> tuple[PairVerdict, ...]:
    """One :class:`PairVerdict` per summary, judged against the bar.

    Uses :meth:`Bar.for_pair` to fetch the thresholds for each ``(suite, candidate)``
    pair, then checks the three bar dimensions. ``met`` is true only when none of the
    three reasons fire; equal to the threshold counts as clear.
    """
    verdicts: list[PairVerdict] = []
    for summary in summaries:
        thresholds = bar.for_pair(summary.suite, summary.candidate)
        reasons: list[str] = []

        if summary.pass_rate < thresholds.min_pass_rate:
            reasons.append(
                f"pass rate {summary.pass_rate:.2f} is below the bar {thresholds.min_pass_rate:.2f}"
            )
        if summary.p95_latency_ms > thresholds.max_p95_latency_ms:
            reasons.append(
                f"p95 latency {summary.p95_latency_ms:.0f}ms exceeds the bar "
                f"{thresholds.max_p95_latency_ms:.0f}ms"
            )
        if summary.max_tokens_per_case > thresholds.max_tokens_per_case:
            reasons.append(
                f"max tokens {summary.max_tokens_per_case} exceeds the bar "
                f"{thresholds.max_tokens_per_case}"
            )

        verdicts.append(
            PairVerdict(
                summary=summary,
                thresholds=thresholds,
                met=len(reasons) == 0,
                reasons=tuple(reasons),
            )
        )
    return tuple(verdicts)


def exit_code(verdicts: Sequence[PairVerdict]) -> int:
    """Return 0 when every verdict is met, 1 otherwise.

    This is the exit code a CI regression test would use — 0 means the audition
    passed, 1 means at least one pair missed the bar.
    """
    return 0 if all(v.met for v in verdicts) else 1
