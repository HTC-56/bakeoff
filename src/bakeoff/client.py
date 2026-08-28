"""The one HTTP seam.

Every request bakeoff makes to a model endpoint goes through this module — that is a
pre-registered rule (SPEC.md "Seam"), not a style preference. Tests and the README
quickstart point it at the bundled stub (:mod:`bakeoff.stub`); ``scripts/live-check.sh``
points it at a real OpenAI-compatible endpoint. Nothing else in the package imports
``httpx``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_TIMEOUT_S = 60.0

type HttpClient = httpx.AsyncClient
"""The connection-pool type callers pass around.

Exported so the runner can annotate a client without importing ``httpx`` itself —
this module stays the only importer of the HTTP library.
"""


class ClientError(RuntimeError):
    """The endpoint could not be used for this case.

    Covers transport failures, non-2xx responses, and replies that do not have the
    shape of an OpenAI-compatible chat completion. The runner turns these into
    recorded per-case outcomes; they are never allowed to crash an audition.
    """


@dataclass(frozen=True)
class Usage:
    """Token counts as reported by the endpoint. Absent fields are recorded as 0."""

    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class Completion:
    """One chat completion: the text, who produced it, and what it cost."""

    text: str
    model: str
    finish_reason: str
    usage: Usage


def _int_field(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key, 0)
    return value if isinstance(value, int) else 0


def _parse_completion(payload: object) -> Completion:
    """Turn a decoded JSON body into a :class:`Completion` or raise :class:`ClientError`."""
    if not isinstance(payload, dict):
        raise ClientError(f"expected a JSON object, got {type(payload).__name__}")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ClientError("reply has no choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ClientError("choices[0] is not an object")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ClientError("choices[0].message is missing")
    content = message.get("content")
    if not isinstance(content, str):
        raise ClientError("choices[0].message.content is not a string")
    raw_usage = payload.get("usage")
    usage_obj = raw_usage if isinstance(raw_usage, dict) else {}
    model = payload.get("model")
    finish = first.get("finish_reason")
    return Completion(
        text=content,
        model=model if isinstance(model, str) else "",
        finish_reason=finish if isinstance(finish, str) else "",
        usage=Usage(
            prompt_tokens=_int_field(usage_obj, "prompt_tokens"),
            completion_tokens=_int_field(usage_obj, "completion_tokens"),
        ),
    )


def build_payload(
    model: str,
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Build a ``/v1/chat/completions`` request body. Pure — safe to assert on in tests."""
    messages: list[dict[str, str]] = []
    if system is not None:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    return payload


async def chat_completion(
    client: HttpClient,
    base_url: str,
    model: str,
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> Completion:
    """POST one chat completion and parse the reply.

    ``base_url`` is the endpoint root (``http://localhost:8000``); the
    ``/v1/chat/completions`` path is appended here so no caller has to know it.
    """
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    payload = build_payload(
        model, prompt, system=system, temperature=temperature, max_tokens=max_tokens
    )
    try:
        response = await client.post(url, json=payload, timeout=timeout)
    except httpx.HTTPError as exc:
        raise ClientError(f"transport error talking to {url}: {exc}") from exc
    if response.status_code >= 400:
        body = response.text[:200]
        raise ClientError(f"{url} returned HTTP {response.status_code}: {body}")
    try:
        decoded: object = response.json()
    except ValueError as exc:
        raise ClientError(f"{url} returned a body that is not JSON") from exc
    return _parse_completion(decoded)


@asynccontextmanager
async def open_client(*, timeout: float = DEFAULT_TIMEOUT_S) -> AsyncIterator[HttpClient]:
    """Open the one pooled client an audition uses, and close it on the way out.

    Callers that already have a client (tests, a long-lived CLI process) pass theirs
    instead; this is the seam's own constructor so nothing else has to name ``httpx``.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        yield client
