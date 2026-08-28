"""The runner.

SPEC.md feature 5: ask every candidate every case of every suite it is entered in,
over async HTTP, with retries and backoff, a per-candidate concurrency cap, and a
timeout — then grade the reply and record what it cost. The promise that shapes this
module is the last clause of the feature: *refusals, timeouts, and malformed replies
are first-class recorded outcomes, never crashes.* Every endpoint problem becomes a
:class:`CaseOutcome` with ``error`` set and ``passed`` false; nothing propagates out
of :func:`run_audition` except an author error (a broken grader spec), which is a bug
in the audition, not a result.

Shape::

    run_audition(audition)          # every candidate x every suite
      -> run_pair(client, cand, s)  # one candidate on one suite, concurrency-capped
        -> run_case(...)            # one prompt, retried, graded, timed

All HTTP goes through :mod:`bakeoff.client` — this module never imports ``httpx``.
Aggregation (pass rates, percentiles, the bar comparison) is *not* here; it lives in
:mod:`bakeoff.scoring`, which takes the outcomes this module produces.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from .client import DEFAULT_TIMEOUT_S, ClientError, HttpClient, chat_completion, open_client
from .manifest import Audition, Candidate
from .suite import Case, Suite, run_grader

Sleeper = Callable[[float], Awaitable[None]]
"""How the runner waits between retries. Injectable so tests never really sleep."""


@dataclass(frozen=True)
class RetryPolicy:
    """How hard to try one case before recording it as an error.

    ``max_attempts`` counts the first try, so ``3`` means one call plus two retries.
    Backoff is exponential: the wait before attempt *n* is
    ``backoff_base_s * backoff_factor ** (n - 2)``, and attempt 1 never waits.
    """

    max_attempts: int = 3
    backoff_base_s: float = 0.25
    backoff_factor: float = 2.0
    timeout_s: float = DEFAULT_TIMEOUT_S

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.backoff_base_s < 0.0:
            raise ValueError("backoff_base_s must not be negative")
        if self.backoff_factor < 1.0:
            raise ValueError("backoff_factor must be at least 1.0")
        if self.timeout_s <= 0.0:
            raise ValueError("timeout_s must be positive")

    def delay_before(self, attempt: int) -> float:
        """Seconds to wait before attempt ``attempt`` (1-based). Attempt 1 waits 0."""
        if attempt <= 1:
            return 0.0
        return self.backoff_base_s * (self.backoff_factor ** (attempt - 2))


@dataclass(frozen=True)
class CaseOutcome:
    """What happened to one case on one candidate — the runner's unit of record.

    ``latency_ms`` is wall time for the whole case including any retries, because
    that is what a user of the endpoint actually waited. ``error`` is ``None`` when
    the endpoint answered at all; when it is set, ``completion`` is empty and the
    case counts as failed.
    """

    candidate: str
    suite: str
    case_id: str
    prompt: str
    completion: str
    passed: bool
    score: float
    detail: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    attempts: int
    error: str | None = None
    finish_reason: str = ""

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def errored(self) -> bool:
        return self.error is not None


@dataclass(frozen=True)
class RunResults:
    """Every outcome of one audition run, plus when it happened.

    Timestamps are ISO-8601 UTC strings so they survive a round trip through
    ``results.json`` unchanged.
    """

    outcomes: tuple[CaseOutcome, ...]
    started_at: str
    finished_at: str

    def __len__(self) -> int:
        return len(self.outcomes)


def _utc_now() -> str:
    """The current time as an ISO-8601 UTC string, seconds resolution."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


async def run_case(
    client: HttpClient,
    candidate: Candidate,
    suite_name: str,
    case: Case,
    *,
    policy: RetryPolicy | None = None,
    sleep: Sleeper = asyncio.sleep,
) -> CaseOutcome:
    """Ask one candidate one case, retrying transport and endpoint failures.

    A :class:`~bakeoff.client.ClientError` — transport failure, non-2xx status,
    timeout, or a reply that is not a chat completion — is retried up to
    ``policy.max_attempts`` times and then recorded as an errored outcome. A reply
    that arrives is graded, however bad it is: a refusal is simply a failing grade.
    """
    active = policy or RetryPolicy()
    profile = candidate.profile
    started = time.perf_counter()
    last_error = "no attempt was made"
    for attempt in range(1, active.max_attempts + 1):
        delay = active.delay_before(attempt)
        if delay > 0.0:
            await sleep(delay)
        try:
            completion = await chat_completion(
                client,
                candidate.base_url,
                candidate.model,
                case.prompt,
                system=profile.system,
                temperature=profile.temperature,
                max_tokens=profile.max_tokens,
                timeout=active.timeout_s,
            )
        except ClientError as exc:
            last_error = str(exc)
            continue
        grade = run_grader(case.grader, completion.text)
        return CaseOutcome(
            candidate=candidate.name,
            suite=suite_name,
            case_id=case.id,
            prompt=case.prompt,
            completion=completion.text,
            passed=grade.passed,
            score=grade.score,
            detail=grade.detail,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            prompt_tokens=completion.usage.prompt_tokens,
            completion_tokens=completion.usage.completion_tokens,
            attempts=attempt,
            error=None,
            finish_reason=completion.finish_reason,
        )
    return CaseOutcome(
        candidate=candidate.name,
        suite=suite_name,
        case_id=case.id,
        prompt=case.prompt,
        completion="",
        passed=False,
        score=0.0,
        detail=f"no usable reply after {active.max_attempts} attempt(s)",
        latency_ms=(time.perf_counter() - started) * 1000.0,
        prompt_tokens=0,
        completion_tokens=0,
        attempts=active.max_attempts,
        error=last_error,
        finish_reason="",
    )


async def run_pair(
    client: HttpClient,
    candidate: Candidate,
    suite: Suite,
    *,
    policy: RetryPolicy | None = None,
    sleep: Sleeper = asyncio.sleep,
    limit: asyncio.Semaphore | None = None,
) -> tuple[CaseOutcome, ...]:
    """Run one candidate over one suite, at most ``profile.concurrency`` cases at once.

    Outcomes come back in suite (file) order however the cases interleave. ``limit``
    lets :func:`run_audition` share one semaphore across a candidate's suites, so the
    cap is per candidate rather than per pair.
    """
    gate = limit or asyncio.Semaphore(candidate.profile.concurrency)

    async def one(case: Case) -> CaseOutcome:
        async with gate:
            return await run_case(client, candidate, suite.name, case, policy=policy, sleep=sleep)

    return tuple(await asyncio.gather(*(one(case) for case in suite.cases)))


async def _run_every_pair(
    client: HttpClient,
    audition: Audition,
    *,
    policy: RetryPolicy | None,
    sleep: Sleeper,
) -> tuple[CaseOutcome, ...]:
    """Every candidate x every suite, each candidate holding its own concurrency cap."""
    limits = {
        c.name: asyncio.Semaphore(c.profile.concurrency) for c in audition.manifest.candidates
    }
    pairs = [
        run_pair(client, candidate, suite, policy=policy, sleep=sleep, limit=limits[candidate.name])
        for candidate in audition.manifest.candidates
        for suite in audition.suites
    ]
    collected: Iterable[tuple[CaseOutcome, ...]] = await asyncio.gather(*pairs)
    return tuple(outcome for group in collected for outcome in group)


async def run_audition(
    audition: Audition,
    *,
    policy: RetryPolicy | None = None,
    client: HttpClient | None = None,
    sleep: Sleeper = asyncio.sleep,
) -> RunResults:
    """Run a whole audition and return every outcome, in candidate then suite order.

    Pass ``client`` to reuse an open connection pool; otherwise one is opened for the
    run and closed afterwards.
    """
    active = policy or RetryPolicy()
    started_at = _utc_now()
    if client is not None:
        outcomes = await _run_every_pair(client, audition, policy=active, sleep=sleep)
    else:
        async with open_client(timeout=active.timeout_s) as owned:
            outcomes = await _run_every_pair(owned, audition, policy=active, sleep=sleep)
    return RunResults(outcomes=outcomes, started_at=started_at, finished_at=_utc_now())


def run_audition_sync(
    audition: Audition,
    *,
    policy: RetryPolicy | None = None,
) -> RunResults:
    """Blocking :func:`run_audition`, for callers that are not async (the CLI, tests)."""
    return asyncio.run(run_audition(audition, policy=policy))
