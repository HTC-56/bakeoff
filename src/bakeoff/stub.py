"""The bundled stub OpenAI-compatible server.

The whole test suite and the README quickstart audition run against this, so CI needs
no model and makes no network call. Replies are canned and deterministic: the same
prompt always produces the same completion and the same usage counts, which is what
lets an audition of the stub be asserted on.

Run it standalone for the quickstart::

    python -m bakeoff.stub --port 8000

Prompt rules are in :func:`canned_reply`.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

STUB_MODEL_SUFFIX = "-stub"
DEFAULT_REPLY = "bakeoff stub reply"


def canned_reply(prompt: str) -> str:
    """Map a user prompt to this stub's deterministic completion.

    Rules, in order:

    * ``echo: <text>`` -> ``<text>`` — the workhorse: lets a suite state its own
      expected answer, so exact/contains/regex cases can be made to pass or fail on
      purpose.
    * ``json: <text>`` -> ``<text>`` unchanged, for cases that grade structure.
    * ``fail: ...`` -> the empty string, so a suite can hold a case that must fail.
    * anything else -> :data:`DEFAULT_REPLY`.
    """
    text = prompt.strip()
    if text.startswith("echo:"):
        return text[len("echo:") :].strip()
    if text.startswith("json:"):
        return text[len("json:") :].strip()
    if text.startswith("fail:"):
        return ""
    return DEFAULT_REPLY


def malformed_reply(prompt: str) -> dict[str, Any] | None:
    """Return a non-chat-completion body when the prompt carries a ``malformed:`` prefix.

    The stripped prompt must start with ``malformed:`` (e.g. ``malformed: anything``).
    Returns a small dict that is valid JSON but has no ``choices`` key, or ``None``
    when the prefix is absent.
    """

    text = prompt.strip()
    if not text.startswith("malformed:"):
        return None
    return {"error": {"message": "malformed reply from model"}}


def error_status(prompt: str) -> int | None:
    """Return an HTTP status code when the prompt carries a ``status:<NNN>:`` prefix.

    The stripped prompt must start with ``status:``, followed by exactly three
    digits, then a colon (e.g. ``status:503: anything``).  Returns the integer
    status code, or ``None`` when the prefix is absent or malformed.
    """

    text = prompt.strip()
    if not text.startswith("status:"):
        return None
    rest = text[len("status:") :]
    if len(rest) < 4 or not rest[:3].isdigit() or rest[3] != ":":
        return None
    return int(rest[:3])


def count_tokens(text: str) -> int:
    """This stub's token model: one token per whitespace-separated word. Deterministic."""
    return len(text.split())


def last_user_prompt(payload: dict[str, Any]) -> str:
    """The content of the last ``user`` message, or ``""`` when there is none."""
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, str):
                return content
    return ""


def build_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Build the full chat-completion body for a request. Pure — tests assert on it."""
    prompt = last_user_prompt(payload)
    reply = canned_reply(prompt)
    model = payload.get("model")
    prompt_tokens = sum(
        count_tokens(m["content"])
        for m in payload.get("messages", [])
        if isinstance(m, dict) and isinstance(m.get("content"), str)
    )
    completion_tokens = count_tokens(reply)
    return {
        "id": "chatcmpl-stub",
        "object": "chat.completion",
        "created": 0,
        "model": model if isinstance(model, str) else "unknown",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


class StubHandler(BaseHTTPRequestHandler):
    """Serves ``POST /v1/chat/completions``. Anything else is a 404."""

    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        """Silence the default stderr access log — tests are noisy enough."""

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:
        # Drain the body first, always. On a keep-alive connection an unread body is
        # parsed as the next request line, which turns a clean 404 into a broken socket.
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if self.path.rstrip("/") != "/v1/chat/completions":
            self._send_json(404, {"error": {"message": f"no such path: {self.path}"}})
            return
        try:
            decoded: object = json.loads(raw or b"{}")
        except ValueError:
            self._send_json(400, {"error": {"message": "request body is not JSON"}})
            return
        if not isinstance(decoded, dict):
            self._send_json(400, {"error": {"message": "request body is not an object"}})
            return
        err_code = error_status(last_user_prompt(decoded))
        if err_code is not None:
            self._send_json(
                err_code,
                {"error": {"message": f"stub error {err_code}"}},
            )
            return
        malformed = malformed_reply(last_user_prompt(decoded))
        if malformed is not None:
            self._send_json(200, malformed)
            return
        self._send_json(200, build_response(decoded))


@contextmanager
def run_stub(host: str = "127.0.0.1", port: int = 0) -> Iterator[str]:
    """Run the stub in a background thread; yield its base URL. Use in tests and fixtures.

    Port 0 asks the OS for a free port, so parallel test sessions never collide.
    """
    server = ThreadingHTTPServer((host, port), StubHandler)
    bound_port = int(server.socket.getsockname()[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{bound_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m bakeoff.stub``. Blocks until interrupted."""
    parser = argparse.ArgumentParser(description="Run the bundled bakeoff stub server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    with run_stub(args.host, args.port) as base_url:
        print(f"bakeoff stub listening on {base_url}", flush=True)
        with contextlib.suppress(KeyboardInterrupt):
            threading.Event().wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
