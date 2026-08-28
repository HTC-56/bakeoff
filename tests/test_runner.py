"""Runner tests: retries, backoff, the concurrency cap, and errors as outcomes.

These drive the runner through a fake transport (:class:`httpx.MockTransport`) so a
test can make the endpoint fail twice and then succeed — something the deterministic
bundled stub cannot do. No socket is opened and no network is touched. The
stub-backed end-to-end tests live alongside these in ``TestRunAuditionEndToEnd``.

Mirror :func:`fake_client` when a new test needs a scripted endpoint.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from bakeoff.manifest import Audition, Candidate, Manifest
from bakeoff.runner import (
    CaseOutcome,
    RetryPolicy,
    RunResults,
    run_audition,
    run_case,
    run_pair,
)
from bakeoff.suite import Case, Suite

Handler = Callable[[httpx.Request], Any]


def completion_body(text: str, *, prompt_tokens: int = 3, completion_tokens: int = 1) -> str:
    """A minimal well-formed chat-completion body, as JSON text."""
    return json.dumps(
        {
            "model": "fake-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }
    )


def fake_client(handler: Handler) -> httpx.AsyncClient:
    """An AsyncClient whose every request is answered by ``handler``. No sockets."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def make_candidate(name: str = "fake", concurrency: int = 4) -> Candidate:
    return Candidate.model_validate(
        {
            "name": name,
            "base_url": "http://localhost:9999",
            "model": "fake-model",
            "profile": {"temperature": 0.0, "concurrency": concurrency},
        }
    )


def make_case(case_id: str = "c1", prompt: str = "echo: 4", expected: str = "4") -> Case:
    return Case.model_validate(
        {"id": case_id, "prompt": prompt, "grader": {"kind": "exact", "expected": expected}}
    )


def make_suite(name: str = "smoke", count: int = 1) -> Suite:
    cases = tuple(make_case(f"c{index}") for index in range(count))
    return Suite(name=name, path=Path("suites") / name, cases=cases)


def make_audition(candidates: int = 1, cases: int = 2) -> Audition:
    manifest = Manifest.model_validate(
        {
            "version": 1,
            "candidates": [
                {
                    "name": f"cand{index}",
                    "base_url": "http://localhost:9999",
                    "model": "fake-model",
                }
                for index in range(candidates)
            ],
            "suites": [{"name": "smoke", "path": "suites/smoke"}],
            "bar": {
                "defaults": {
                    "min_pass_rate": 1.0,
                    "max_p95_latency_ms": 5000,
                    "max_tokens_per_case": 100,
                }
            },
        }
    )
    return Audition(manifest=manifest, suites=(make_suite(count=cases),))


class RecordingSleeper:
    """A drop-in for ``asyncio.sleep`` that records the delays instead of waiting."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


class TestRetryPolicy:
    def test_the_first_attempt_never_waits(self) -> None:
        assert RetryPolicy().delay_before(1) == 0.0

    def test_backoff_is_exponential_from_the_base(self) -> None:
        policy = RetryPolicy(backoff_base_s=0.5, backoff_factor=2.0)
        assert policy.delay_before(2) == 0.5
        assert policy.delay_before(3) == 1.0
        assert policy.delay_before(4) == 2.0

    def test_a_policy_that_never_tries_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_attempts"):
            RetryPolicy(max_attempts=0)

    def test_a_shrinking_backoff_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="backoff_factor"):
            RetryPolicy(backoff_factor=0.5)


class TestRunCaseRetries:
    def _run(self, handler: Handler, policy: RetryPolicy, sleeper: RecordingSleeper) -> CaseOutcome:
        async def go() -> CaseOutcome:
            async with fake_client(handler) as client:
                return await run_case(
                    client, make_candidate(), "smoke", make_case(), policy=policy, sleep=sleeper
                )

        return asyncio.run(go())

    def test_a_flaky_endpoint_is_retried_until_it_answers(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) < 3:
                return httpx.Response(503, json={"error": {"message": "busy"}})
            return httpx.Response(200, text=completion_body("4"))

        sleeper = RecordingSleeper()
        outcome = self._run(handler, RetryPolicy(max_attempts=3, backoff_base_s=0.1), sleeper)
        assert outcome.attempts == 3
        assert outcome.error is None
        assert outcome.passed is True
        assert sleeper.delays == [0.1, 0.2]

    def test_a_dead_endpoint_becomes_a_recorded_outcome_not_an_exception(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"error": {"message": "busy"}})

        outcome = self._run(
            handler, RetryPolicy(max_attempts=2, backoff_base_s=0.0), RecordingSleeper()
        )
        assert outcome.errored is True
        assert outcome.passed is False
        assert outcome.score == 0.0
        assert outcome.completion == ""
        assert outcome.attempts == 2
        assert "503" in (outcome.error or "")

    def test_a_malformed_reply_is_retried_then_recorded(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"not": "a completion"})

        outcome = self._run(
            handler, RetryPolicy(max_attempts=2, backoff_base_s=0.0), RecordingSleeper()
        )
        assert outcome.errored is True
        assert "choices" in (outcome.error or "")

    def test_a_refusal_is_graded_not_errored(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=completion_body("I cannot help with that."))

        outcome = self._run(handler, RetryPolicy(), RecordingSleeper())
        assert outcome.error is None
        assert outcome.attempts == 1
        assert outcome.passed is False
        assert outcome.completion.startswith("I cannot")

    def test_usage_and_latency_are_captured(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, text=completion_body("4", prompt_tokens=7, completion_tokens=2)
            )

        outcome = self._run(handler, RetryPolicy(), RecordingSleeper())
        assert outcome.prompt_tokens == 7
        assert outcome.completion_tokens == 2
        assert outcome.total_tokens == 9
        assert outcome.latency_ms >= 0.0


class TestRunPairConcurrency:
    def test_no_more_than_the_profile_cap_are_in_flight_at_once(self) -> None:
        state = {"live": 0, "peak": 0}

        async def handler(request: httpx.Request) -> httpx.Response:
            state["live"] += 1
            state["peak"] = max(state["peak"], state["live"])
            await asyncio.sleep(0.01)
            state["live"] -= 1
            return httpx.Response(200, text=completion_body("4"))

        async def go() -> tuple[CaseOutcome, ...]:
            async with fake_client(handler) as client:
                return await run_pair(client, make_candidate(concurrency=2), make_suite(count=6))

        outcomes = asyncio.run(go())
        assert len(outcomes) == 6
        assert state["peak"] <= 2
        assert all(outcome.passed for outcome in outcomes)

    def test_outcomes_come_back_in_suite_order(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(0.001)
            return httpx.Response(200, text=completion_body("4"))

        async def go() -> tuple[CaseOutcome, ...]:
            async with fake_client(handler) as client:
                return await run_pair(client, make_candidate(concurrency=4), make_suite(count=5))

        outcomes = asyncio.run(go())
        assert [outcome.case_id for outcome in outcomes] == ["c0", "c1", "c2", "c3", "c4"]


class TestRunAudition:
    def _run(self, audition: Audition, handler: Handler) -> RunResults:
        async def go() -> RunResults:
            async with fake_client(handler) as client:
                return await run_audition(audition, client=client)

        return asyncio.run(go())

    def test_every_candidate_meets_every_case(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=completion_body("4"))

        results = self._run(make_audition(candidates=2, cases=3), handler)
        assert len(results) == 6
        assert {outcome.candidate for outcome in results.outcomes} == {"cand0", "cand1"}
        assert all(outcome.suite == "smoke" for outcome in results.outcomes)

    def test_a_run_records_when_it_started_and_finished(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=completion_body("4"))

        results = self._run(make_audition(), handler)
        assert results.started_at.endswith("+00:00")
        assert results.finished_at >= results.started_at

    def test_a_failing_endpoint_never_crashes_the_audition(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": {"message": "boom"}})

        audition = make_audition(candidates=2, cases=2)
        results = self._run(audition, handler)
        assert len(results) == 4
        assert all(outcome.errored for outcome in results.outcomes)
