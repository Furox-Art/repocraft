"""Tests for the craft path; the model is mocked, the gates are real."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

import pytest

from repocraft.craft import (
    CraftResult,
    craft_prompt,
    parse_craft,
    request_craft,
    verify_craft,
)
from repocraft.errors import CraftError

GOOD_CODE = '''"""Addition utilities."""


def add(left: int, right: int) -> int:
    """Return the sum of two integers."""
    return left + right
'''

GOOD_TEST = '''"""Tests for adder."""

import unittest

import adder


class AdderTests(unittest.TestCase):
    def test_adds(self) -> None:
        self.assertEqual(adder.add(2, 3), 5)


if __name__ == "__main__":
    unittest.main()
'''

FAILING_TEST = GOOD_TEST.replace("adder.add(2, 3), 5", "adder.add(2, 3), 6")

OTHER_IMPORT_TEST = GOOD_TEST.replace("import adder", "import json")

NO_TESTS_TEST = '''"""No tests here."""

import unittest

import adder


if __name__ == "__main__":
    unittest.main()
'''


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _reply(content: Any) -> dict[str, Any]:
    return {"choices": [{"message": {"content": content}}]}


def _install_urlopen(
    monkeypatch: pytest.MonkeyPatch, payload: Any, capture: dict[str, Any]
) -> None:
    def fake(request: urllib.request.Request, timeout: int) -> _FakeResponse:
        capture["url"] = request.full_url
        body = request.data
        assert isinstance(body, bytes)
        capture["body"] = json.loads(body.decode("utf-8"))
        if isinstance(payload, Exception):
            raise payload
        return _FakeResponse(payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake)


def _craft_reply() -> str:
    return json.dumps({"name": "adder", "code": GOOD_CODE, "test": GOOD_TEST})


def test_craft_prompt_describes_the_strict_reply() -> None:
    prompt = craft_prompt()
    assert "Reply with JSON only" in prompt
    assert "unittest" in prompt
    assert "standard library" in prompt


def test_parse_craft_accepts_a_well_formed_reply() -> None:
    result = parse_craft(_craft_reply())
    assert result.name == "adder"
    assert result.code == GOOD_CODE
    assert result.test == GOOD_TEST


@pytest.mark.parametrize(
    ("name", "code", "test", "fragment"),
    [
        ("Adder", GOOD_CODE, GOOD_TEST, "snake_case"),
        ("1bad", GOOD_CODE, GOOD_TEST, "snake_case"),
        ("with-dash", GOOD_CODE, GOOD_TEST, "snake_case"),
        ("class", GOOD_CODE, GOOD_TEST, "snake_case"),
        ("", GOOD_CODE, GOOD_TEST, "snake_case"),
        ("adder", "", GOOD_TEST, "non-empty code and test"),
        ("adder", GOOD_CODE, "   ", "non-empty code and test"),
        ("adder", 5, GOOD_TEST, "non-empty code and test"),
        ("adder", GOOD_CODE, None, "non-empty code and test"),
    ],
)
def test_parse_craft_rejects_malformed_replies(
    name: Any, code: Any, test: Any, fragment: str
) -> None:
    with pytest.raises(CraftError, match=fragment):
        parse_craft(json.dumps({"name": name, "code": code, "test": test}))


def test_parse_craft_wraps_intent_errors() -> None:
    with pytest.raises(CraftError, match="contains no JSON"):
        parse_craft("not json at all")


def test_verify_craft_runs_every_gate() -> None:
    verified = verify_craft(CraftResult(name="adder", code=GOOD_CODE, test=GOOD_TEST))

    assert verified.result.name == "adder"
    assert verified.checks[0] == "python syntax"
    assert "test imports the module" in verified.checks
    assert verified.checks[-1] == "unit tests pass"


def test_verify_craft_skips_ruff_when_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("repocraft.craft._ruff_available", lambda: False)

    verified = verify_craft(CraftResult(name="adder", code=GOOD_CODE, test=GOOD_TEST))

    assert "ruff" not in verified.checks


def test_verify_craft_can_disable_ruff() -> None:
    verified = verify_craft(
        CraftResult(name="adder", code=GOOD_CODE, test=GOOD_TEST), run_ruff=False
    )

    assert "ruff" not in verified.checks


@pytest.mark.parametrize(
    ("code", "test", "fragment"),
    [
        ("def broken(:", GOOD_TEST, "syntax error"),
        (GOOD_CODE, "def broken(:", "syntax error"),
        (GOOD_CODE, OTHER_IMPORT_TEST, "must import the module"),
        (GOOD_CODE, FAILING_TEST, "generated tests failed"),
        (
            "import os\n\n\ndef add(left: int, right: int) -> int:\n"
            '    """Return the sum."""\n    return left + right\n',
            GOOD_TEST,
            "ruff rejected",
        ),
    ],
)
def test_verify_craft_rejects_failed_gates(
    code: str, test: str, fragment: str
) -> None:
    with pytest.raises(CraftError, match=fragment):
        verify_craft(CraftResult(name="adder", code=code, test=test))


def test_verify_craft_rejects_test_files_without_tests() -> None:
    with pytest.raises(CraftError, match="contains no tests"):
        verify_craft(
            CraftResult(name="adder", code=GOOD_CODE, test=NO_TESTS_TEST),
            run_ruff=False,
        )


def test_request_craft_returns_the_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    capture: dict[str, Any] = {}
    _install_urlopen(monkeypatch, _reply(_craft_reply()), capture)

    result = request_craft("a small adder", api_key="secret")

    assert result == CraftResult(name="adder", code=GOOD_CODE, test=GOOD_TEST)
    assert capture["url"] == "https://api.openai.com/v1/chat/completions"
    assert capture["body"]["model"] == "gpt-4o-mini"
    assert capture["body"]["messages"][1] == {"role": "user", "content": "a small adder"}
    assert "You write single-file" in capture["body"]["messages"][0]["content"]


def test_request_craft_reads_configuration_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture: dict[str, Any] = {}
    _install_urlopen(monkeypatch, _reply(_craft_reply()), capture)
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://env.example/v1")
    monkeypatch.setenv("REPOCRAFT_MODEL", "env-model")

    result = request_craft("a small adder")

    assert result.name == "adder"
    assert capture["url"] == "https://env.example/v1/chat/completions"
    assert capture["body"]["model"] == "env-model"


def test_request_craft_requires_an_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(CraftError, match="OPENAI_API_KEY is not set"):
        request_craft("a small adder")


@pytest.mark.parametrize(
    ("payload", "fragment"),
    [
        (urllib.error.URLError("boom"), "cannot reach the endpoint"),
        ({}, "unexpected response shape"),
        (_reply("not json"), "contains no JSON"),
        (_reply('{"name": "Adder", "code": "x = 1", "test": "import adder"}'), "snake_case"),
    ],
)
def test_request_craft_reports_failures(
    monkeypatch: pytest.MonkeyPatch, payload: Any, fragment: str
) -> None:
    capture: dict[str, Any] = {}
    _install_urlopen(monkeypatch, payload, capture)

    with pytest.raises(CraftError, match=fragment):
        request_craft("a small adder", api_key="secret")
