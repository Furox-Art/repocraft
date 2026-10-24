"""HTTP-layer tests for ask/craft against a real local chat-completions server.

These tests exercise the genuine network path — sockets, headers, status
codes, timeouts — against a loopback server, so no API key or remote
endpoint is needed.
"""

from __future__ import annotations

import http.server
import json
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from repocraft.craft import request_craft
from repocraft.errors import CraftError, IntentError
from repocraft.intent import post_chat, request_intent
from repocraft.recipe import load_recipes

RECIPES = load_recipes()


class _ChatServer(http.server.ThreadingHTTPServer):
    """Loopback chat-completions endpoint with a scripted response."""

    def __init__(self, address: tuple[str, int]) -> None:
        super().__init__(address, _ChatHandler)
        self.requests: list[dict[str, Any]] = []
        self.respond: Callable[[], tuple[int, Any]] = lambda: (
            200,
            {"choices": [{"message": {"content": "{}"}}]},
        )
        self.delay_seconds = 0.0


class _ChatHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        server = self.server
        assert isinstance(server, _ChatServer)
        server.requests.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "content_type": self.headers.get("Content-Type"),
                "body": body,
            }
        )
        if server.delay_seconds > 0:
            time.sleep(server.delay_seconds)
        status, payload = server.respond()
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        return None


@pytest.fixture()
def chat_server() -> Iterator[_ChatServer]:
    server = _ChatServer(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _base_url(server: _ChatServer) -> str:
    address = server.server_address
    host = address[0]
    port = address[1]
    assert isinstance(host, str)
    assert isinstance(port, int)
    return f"http://{host}:{port}/v1"


def _intent_reply(content: str) -> tuple[int, Any]:
    return 200, {"choices": [{"message": {"content": content}}]}


_ADDER_CODE = (
    "def add(a: int, b: int) -> int:\n"
    '    """Sum."""\n'
    "    return a + b\n"
)

_ADDER_TEST = (
    "import unittest\n\nimport adder\n\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_adds(self) -> None:\n"
    "        self.assertEqual(adder.add(2, 3), 5)\n\n\n"
    'if __name__ == "__main__":\n'
    "    unittest.main()\n"
)


def test_ask_intent_travels_over_real_http(chat_server: _ChatServer) -> None:
    server = chat_server
    server.respond = lambda: _intent_reply(
        '{"recipe": "triangle", "parameters": {"height": 9}}'
    )

    intent = request_intent(
        "a tall triangle",
        RECIPES,
        api_key="secret-key",
        base_url=_base_url(server),
    )

    assert intent.recipe.id == "triangle"
    assert intent.parameters == {"height": 9}
    request = server.requests[0]
    assert request is not None
    assert request["path"] == "/v1/chat/completions"
    assert request["authorization"] == "Bearer secret-key"
    assert request["content_type"] == "application/json"
    assert request["body"]["model"] == "gpt-4o-mini"
    assert request["body"]["temperature"] == 0
    assert request["body"]["messages"][1] == {
        "role": "user",
        "content": "a tall triangle",
    }


def test_craft_travels_over_real_http(chat_server: _ChatServer) -> None:
    server = chat_server
    server.respond = lambda: _intent_reply(
        json.dumps({"name": "adder", "code": _ADDER_CODE, "test": _ADDER_TEST})
    )

    result = request_craft(
        "a small adder", api_key="secret-key", base_url=_base_url(server)
    )

    assert result.name == "adder"
    assert "def add" in result.code
    request = server.requests[0]
    assert request is not None
    assert request["body"]["messages"][1] == {
        "role": "user",
        "content": "a small adder",
    }


def test_http_error_reports_the_status(chat_server: _ChatServer) -> None:
    server = chat_server
    server.respond = lambda: (401, {"error": {"message": "bad key"}})

    with pytest.raises(IntentError, match="HTTP 401"):
        request_intent(
            "triangle", RECIPES, api_key="bad", base_url=_base_url(server)
        )


def test_http_500_is_reported(chat_server: _ChatServer) -> None:
    server = chat_server
    server.respond = lambda: (500, {"error": {"message": "boom"}})

    with pytest.raises(CraftError, match="HTTP 500"):
        request_craft("adder", api_key="k", base_url=_base_url(server))


def test_non_json_body_is_reported(chat_server: _ChatServer) -> None:
    server = chat_server
    server.respond = lambda: (200, {"unexpected": "shape"})

    with pytest.raises(IntentError, match="unexpected response shape"):
        request_intent(
            "triangle", RECIPES, api_key="k", base_url=_base_url(server)
        )


def test_unreachable_endpoint_is_reported() -> None:
    # A closed port: the refused connection exercises the real network path.
    with pytest.raises(IntentError, match="cannot reach the endpoint"):
        post_chat(
            url="http://127.0.0.1:9/chat/completions",
            api_key="k",
            model="m",
            messages=[{"role": "user", "content": "hi"}],
        )


def test_timeout_is_reported(chat_server: _ChatServer) -> None:
    server = chat_server
    server.delay_seconds = 1.5

    started = time.monotonic()
    with pytest.raises(IntentError, match="cannot reach the endpoint"):
        post_chat(
            url=f"{_base_url(server)}/chat/completions",
            api_key="k",
            model="m",
            messages=[{"role": "user", "content": "hi"}],
            timeout=0.3,
        )
    assert time.monotonic() - started < 1.2
