"""Pure graders.

A grader takes a model completion plus its spec and returns a :class:`GradeResult`.
Every grader in this module is a pure function: no I/O, no clock, no randomness, no
network. That is the point — a grader bug is a test failure here, not audit noise in
a report.

Adding a grader: write one function, ``grade_<name>(completion, ...) -> GradeResult``,
mirroring :func:`grade_exact` below, and give it a test class in
``tests/test_graders.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


class GraderConfigError(ValueError):
    """A grader spec is malformed — e.g. a pattern that does not compile.

    Raised at grade time and treated as an audition-author error, never as a
    failing case: a broken grader spec must not quietly score zero.
    """


@dataclass(frozen=True)
class GradeResult:
    """The outcome of grading one completion.

    ``score`` is in ``[0.0, 1.0]``; binary graders use ``1.0``/``0.0``. ``detail`` is
    a short human-readable reason, shown in the report's per-case drill-down.
    """

    passed: bool
    score: float
    detail: str


def _binary(passed: bool, detail: str) -> GradeResult:
    """Build a pass/fail result. Shared by every binary grader in this module."""
    return GradeResult(passed=passed, score=1.0 if passed else 0.0, detail=detail)


def grade_exact(completion: str, expected: str, *, strip: bool = True) -> GradeResult:
    """Pass when the completion equals ``expected``.

    With ``strip`` (the default) leading and trailing whitespace is ignored on both
    sides, so a model that answers with a trailing newline still passes.
    """
    got = completion.strip() if strip else completion
    want = expected.strip() if strip else expected
    if got == want:
        return _binary(True, "exact match")
    return _binary(False, f"expected {want!r}, got {got!r}")


def grade_contains(
    completion: str,
    substring: str,
    *,
    case_sensitive: bool = True,
) -> GradeResult:
    """Pass when ``substring`` appears anywhere in ``completion``.

    When ``case_sensitive`` is ``False`` both sides are lower-cased before the
    search.  The failure ``detail`` names the missing substring.
    """
    if case_sensitive:
        needle = substring
        haystack = completion
    else:
        needle = substring.lower()
        haystack = completion.lower()
    if needle in haystack:
        return _binary(True, f"contains {substring!r}")
    return _binary(False, f"missing {substring!r}")
