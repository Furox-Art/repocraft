"""Tests for the AI intent layer; no test reaches the network."""

from __future__ import annotations

import email.message
import io
import json
import urllib.error
import urllib.request
from typing import Any

import pytest

from repocraft.errors import IntentError, RecipeError
from repocraft.intent import (
    chat_url,
    parse_intent,
    request_intent,
    system_prompt,
)
from repocraft.recipe import Recipe, load_recipes

RECIPES = load_recipes()


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def read(self) -> bytes:
        if isinstance(self._payload, bytes):
            return self._payload
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _reply(content: Any) -> dict[str, Any]:
    return {"choices": [{"message": {"content": content}}]}


def _recipe(recipe_id: str) -> Recipe:
    return next(recipe for recipe in RECIPES if recipe.id == recipe_id)


def _install_urlopen(
    monkeypatch: pytest.MonkeyPatch, payload: Any, capture: dict[str, Any]
) -> None:
    def fake(request: urllib.request.Request, timeout: int) -> _FakeResponse:
        capture["url"] = request.full_url
        body = request.data
        assert isinstance(body, bytes)
        capture["body"] = json.loads(body.decode("utf-8"))
        capture["timeout"] = timeout
        capture["authorization"] = request.get_header("Authorization")
        if isinstance(payload, Exception):
            raise payload
        return _FakeResponse(payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake)


def test_system_prompt_lists_the_catalog_deterministically() -> None:
    prompt = system_prompt(RECIPES)
    assert "id: triangle | description: Draw a centered ASCII triangle." in prompt
    assert "height (integer, 1..100, default 5)" in prompt
    assert "Reply with JSON only" in prompt
    assert prompt == system_prompt(RECIPES)


def test_chat_url_joins_and_preserves_full_urls() -> None:
    assert chat_url("https://example.com/v1") == "https://example.com/v1/chat/completions"
    assert chat_url("https://example.com/v1/") == "https://example.com/v1/chat/completions"
    assert (
        chat_url("https://example.com/v1/chat/completions")
        == "https://example.com/v1/chat/completions"
    )


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('{"recipe": "triangle", "parameters": {"height": 7}}', {"recipe": "triangle"}),
        ('sure: {"recipe": "triangle"} ok', {"recipe": "triangle"}),
        ('```json\n{"recipe": "pascal"}\n```', {"recipe": "pascal"}),
    ],
)
def test_parse_intent_accepts_plain_and_embedded_json(
    content: str, expected: dict[str, Any]
) -> None:
    parsed = parse_intent(content)
    assert all(parsed[key] == value for key, value in expected.items())


@pytest.mark.parametrize(
    ("content", "fragment"),
    [
        ("no json at all", "contains no JSON"),
        ('broken {"recipe": } tail', "not valid JSON"),
        ("[1, 2]", "must be a JSON object"),
    ],
)
def test_parse_intent_rejects_unusable_replies(content: str, fragment: str) -> None:
    with pytest.raises(IntentError, match=fragment):
        parse_intent(content)


def test_request_intent_returns_a_validated_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture: dict[str, Any] = {}
    _install_urlopen(
        monkeypatch,
        _reply('{"recipe": "triangle", "parameters": {"height": 7}}'),
        capture,
    )

    intent = request_intent("a tall triangle", RECIPES, api_key="secret")

    assert intent.recipe == _recipe("triangle")
    assert intent.parameters == {"height": 7}
    assert capture["url"] == "https://api.openai.com/v1/chat/completions"
    assert capture["authorization"] == "Bearer secret"
    assert capture["timeout"] == 60
    assert capture["body"]["model"] == "gpt-4o-mini"
    assert capture["body"]["temperature"] == 0
    assert capture["body"]["messages"][1] == {"role": "user", "content": "a tall triangle"}
    assert "id: triangle" in capture["body"]["messages"][0]["content"]


def test_request_intent_reads_configuration_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture: dict[str, Any] = {}
    _install_urlopen(monkeypatch, _reply('{"recipe": "pascal"}'), capture)
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://env.example/v1/")
    monkeypatch.setenv("REPOCRAFT_MODEL", "env-model")

    intent = request_intent("pascal rows", RECIPES)

    assert intent.recipe == _recipe("pascal")
    assert intent.parameters == {"rows": 5}
    assert capture["url"] == "https://env.example/v1/chat/completions"
    assert capture["body"]["model"] == "env-model"
    assert capture["authorization"] == "Bearer env-key"


def test_request_intent_requires_an_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(IntentError, match="OPENAI_API_KEY is not set"):
        request_intent("triangle", RECIPES)


@pytest.mark.parametrize(
    ("payload", "fragment"),
    [
        (
            urllib.error.HTTPError(
                "url",
                401,
                "Unauthorized",
                email.message.Message(),
                io.BytesIO(b'{"error": "key"}'),
            ),
            "HTTP 401",
        ),
        (urllib.error.URLError("boom"), "cannot reach the endpoint"),
        (TimeoutError("too slow"), "cannot reach the endpoint"),
        (b"not json at all", "invalid JSON"),
        ({}, "unexpected response shape"),
        ({"choices": []}, "unexpected response shape"),
        ({"choices": [{"message": {"content": None}}]}, "no text content"),
    ],
)
def test_request_intent_reports_endpoint_failures(
    monkeypatch: pytest.MonkeyPatch, payload: Any, fragment: str
) -> None:
    capture: dict[str, Any] = {}
    _install_urlopen(monkeypatch, payload, capture)

    with pytest.raises(IntentError, match=fragment):
        request_intent("triangle", RECIPES, api_key="secret")


@pytest.mark.parametrize(
    ("reply", "fragment"),
    [
        ('{"recipe": null, "reason": "nothing fits"}', "nothing fits"),
        ('{"recipe": null}', "no reason given"),
        ('{"recipe": null, "reason": ""}', "no reason given"),
        ('{"recipe": null, "reason": 42}', "no reason given"),
        ('{"recipe": 5}', "must be a string or null"),
        ('{"recipe": "nope"}', "unknown recipe 'nope'"),
        ('{"recipe": "triangle", "parameters": [1]}', "must be a mapping"),
        ('{"recipe": "triangle", "parameters": {"height": "7"}}', "map names to integers"),
        ('{"recipe": "triangle", "parameters": {"height": true}}', "map names to integers"),
    ],
)
def test_request_intent_rejects_unusable_intents(
    monkeypatch: pytest.MonkeyPatch, reply: str, fragment: str
) -> None:
    capture: dict[str, Any] = {}
    _install_urlopen(monkeypatch, _reply(reply), capture)

    with pytest.raises(IntentError, match=fragment):
        request_intent("anything", RECIPES, api_key="secret")


@pytest.mark.parametrize(
    ("reply", "error", "fragment"),
    [
        ('{"recipe": "triangle", "parameters": {"nope": 7}}', RecipeError, "no parameter"),
        (
            '{"recipe": "triangle", "parameters": {"height": 999999}}',
            RecipeError,
            "between 1 and 100",
        ),
    ],
)
def test_request_intent_still_applies_recipe_parameter_rules(
    monkeypatch: pytest.MonkeyPatch, reply: str, error: type[Exception], fragment: str
) -> None:
    capture: dict[str, Any] = {}
    _install_urlopen(monkeypatch, _reply(reply), capture)

    with pytest.raises(error, match=fragment):
        request_intent("anything", RECIPES, api_key="secret")
