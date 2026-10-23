"""Turn a free-form request into a validated recipe intent with an AI helper.

The model only proposes a ``{recipe, parameters}`` intent as JSON; it never
writes code or files. The proposal is validated against the recipe catalog
with the same rules as ``repocraft make``, so the deterministic core and its
guarantees are unchanged.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from repocraft.errors import IntentError
from repocraft.recipe import Recipe, resolve_parameters

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
_TIMEOUT_SECONDS = 60

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True)
class Intent:
    """A validated intent: one recipe and its resolved parameters."""

    recipe: Recipe
    parameters: dict[str, int]


def system_prompt(recipes: Sequence[Recipe]) -> str:
    """Describe the catalog and the strict reply format; deterministic."""
    lines = [
        "You translate free-form snippet requests into a strict JSON intent.",
        "Available recipes:",
    ]
    for recipe in recipes:
        parameters = ", ".join(
            f"{parameter.name} (integer, {parameter.minimum}..{parameter.maximum},"
            f" default {parameter.default})"
            for parameter in recipe.parameters
        )
        lines.append(
            f"- id: {recipe.id} | description: {recipe.description}"
            f" | parameters: {parameters}"
        )
    lines.append(
        'Reply with JSON only: {"recipe": "<id>", "parameters": {"<name>": <integer>}}.'
        " Use the parameter defaults unless the request clearly states other values"
        ' inside the allowed range. If no single recipe fits, reply'
        ' {"recipe": null, "reason": "<short explanation>"}.'
    )
    return "\n".join(lines)


def chat_url(base_url: str) -> str:
    """Return the chat completions URL for an OpenAI-compatible base URL."""
    if base_url.endswith("/chat/completions"):
        return base_url
    return base_url.rstrip("/") + "/chat/completions"


def parse_intent(content: str) -> dict[str, Any]:
    """Parse the model reply as a JSON object, tolerating markdown fences."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = _JSON_OBJECT.search(content)
        if match is None:
            raise IntentError("the model reply contains no JSON") from None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as error:
            raise IntentError(f"the model reply is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise IntentError("the model reply must be a JSON object")
    return data


def request_intent(
    request: str,
    recipes: Sequence[Recipe],
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> Intent:
    """Ask the model for an intent and validate it against the catalog."""
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise IntentError("OPENAI_API_KEY is not set; the ask command needs it")
    url = chat_url(base_url or os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL)
    chosen_model = model or os.environ.get("REPOCRAFT_MODEL") or DEFAULT_MODEL
    messages = [
        {"role": "system", "content": system_prompt(recipes)},
        {"role": "user", "content": request},
    ]
    payload = post_chat(url=url, api_key=key, model=chosen_model, messages=messages)
    return _validate_intent(parse_intent(chat_content(payload)), recipes)


def post_chat(
    *, url: str, api_key: str, model: str, messages: list[dict[str, str]]
) -> Any:
    """POST a chat completion request and return the decoded JSON payload."""
    body = json.dumps(
        {"model": model, "temperature": 0, "messages": messages}
    ).encode("utf-8")
    http_request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:200]
        raise IntentError(f"the endpoint returned HTTP {error.code}: {detail}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise IntentError(f"cannot reach the endpoint: {error}") from error
    except json.JSONDecodeError as error:
        raise IntentError(f"the endpoint returned invalid JSON: {error}") from error


def chat_content(payload: Any) -> str:
    """Return the text content of a chat completion response payload."""
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise IntentError("unexpected response shape from the endpoint") from error
    if not isinstance(content, str):
        raise IntentError("the endpoint returned no text content")
    return content


def _validate_intent(data: dict[str, Any], recipes: Sequence[Recipe]) -> Intent:
    recipe_id = data.get("recipe")
    if recipe_id is None:
        reason = data.get("reason")
        explanation = reason if isinstance(reason, str) and reason else "no reason given"
        raise IntentError(f"the model rejected the request: {explanation}")
    if not isinstance(recipe_id, str):
        raise IntentError("the intent recipe must be a string or null")
    recipe = next((entry for entry in recipes if entry.id == recipe_id), None)
    if recipe is None:
        raise IntentError(f"the model chose unknown recipe {recipe_id!r}")
    raw_parameters = data.get("parameters", {})
    if not isinstance(raw_parameters, dict):
        raise IntentError("the intent parameters must be a mapping")
    overrides: dict[str, str] = {}
    for name, value in raw_parameters.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise IntentError("the intent parameters must map names to integers")
        overrides[name] = str(value)
    return Intent(recipe=recipe, parameters=resolve_parameters(recipe, overrides))
