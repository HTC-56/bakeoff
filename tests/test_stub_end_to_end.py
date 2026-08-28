"""The Phase A end-to-end proof: client -> bundled stub -> grader, no network.

This is the shape every later runner test follows. Nothing here reaches outside the
loopback interface, and no test in this repo ever may.
"""

from __future__ import annotations

import asyncio

import httpx

from bakeoff.client import ClientError, Completion, build_payload, chat_completion
from bakeoff.graders import grade_exact
from bakeoff.stub import DEFAULT_REPLY, build_response, canned_reply, run_stub


def ask(base_url: str, prompt: str, model: str = "stub-model") -> Completion:
    """Send one prompt to a running stub and return the parsed completion."""

    async def go() -> Completion:
        async with httpx.AsyncClient() as client:
            return await chat_completion(client, base_url, model, prompt)

    return asyncio.run(go())


class TestCannedReply:
    def test_echo_prefix_returns_the_remainder(self) -> None:
        assert canned_reply("echo: 4") == "4"

    def test_fail_prefix_returns_the_empty_string(self) -> None:
        assert canned_reply("fail: whatever") == ""

    def test_an_unrecognised_prompt_gets_the_default_reply(self) -> None:
        assert canned_reply("what is 2 + 2?") == DEFAULT_REPLY

    def test_the_same_prompt_always_gives_the_same_reply(self) -> None:
        assert canned_reply("echo: same") == canned_reply("echo: same")


class TestBuildResponse:
    def test_usage_counts_words_on_both_sides(self) -> None:
        payload = build_payload("m", "echo: two words")
        body = build_response(payload)
        assert body["usage"]["prompt_tokens"] == 3
        assert body["usage"]["completion_tokens"] == 2
        assert body["usage"]["total_tokens"] == 5

    def test_the_requested_model_is_echoed_back(self) -> None:
        assert build_response(build_payload("some-model", "hi"))["model"] == "some-model"


class TestEndToEnd:
    def test_a_prompt_round_trips_through_the_seam_and_grades_clean(self) -> None:
        with run_stub() as base_url:
            completion = ask(base_url, "echo: 4")
        assert completion.text == "4"
        assert completion.finish_reason == "stop"
        assert completion.usage.total_tokens > 0
        assert grade_exact(completion.text, "4").passed is True

    def test_a_failing_case_is_a_failing_grade_not_an_exception(self) -> None:
        with run_stub() as base_url:
            completion = ask(base_url, "fail: this one must miss")
        assert grade_exact(completion.text, "4").passed is False

    def test_a_wrong_path_surfaces_as_a_client_error(self) -> None:
        async def go(base_url: str) -> None:
            async with httpx.AsyncClient() as client:
                await client.post(f"{base_url}/v1/nope", json={})
                await chat_completion(client, f"{base_url}/wrong", "m", "hi")

        with run_stub() as base_url:
            try:
                asyncio.run(go(base_url))
            except ClientError as exc:
                assert "404" in str(exc)
            else:  # pragma: no cover - the stub must 404 unknown paths
                raise AssertionError("expected a ClientError for an unknown path")
