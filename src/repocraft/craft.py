"""Free-form snippets where a model writes the code and repocraft verifies it.

The model proposes a module, its code, and a unittest file as JSON. repocraft
then runs deterministic gates on the proposal: python syntax, a check that the
tests import the module, ruff when it is installed, and the generated tests
themselves. Nothing is written until every gate passes and the user confirms.
"""

from __future__ import annotations

import ast
import importlib.util
import keyword
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from repocraft.errors import CraftError, IntentError
from repocraft.intent import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    chat_content,
    chat_url,
    parse_intent,
    post_chat,
)

_NAME = re.compile(r"^[a-z][a-z0-9_]{0,49}$")
_RAN_TESTS = re.compile(r"Ran (\d+) tests?")


@dataclass(frozen=True)
class CraftResult:
    """The unverified model proposal: a module name, its code, and its test."""

    name: str
    code: str
    test: str


@dataclass(frozen=True)
class VerifiedCraft:
    """A proposal that passed every deterministic gate."""

    result: CraftResult
    checks: tuple[str, ...]


def craft_prompt() -> str:
    """Describe the strict reply format for free-form snippet generation."""
    return (
        "You write single-file Python 3 snippets on request.\n"
        'Reply with JSON only: {"name": "<snake_case module name>",'
        ' "code": "<module source>", "test": "<unittest source>"}.\n'
        "The code must be self-contained, use only the standard library,"
        " and carry type hints and docstrings.\n"
        "Import abstract collection types from collections.abc, not from"
        " typing (for example: from collections.abc import Sequence).\n"
        "The test must import the module by its name, use unittest, and"
        " contain at least one meaningful test."
    )


def parse_craft(content: str) -> CraftResult:
    """Parse and shape-check the model reply; deeper checks happen in verify."""
    try:
        data = parse_intent(content)
    except IntentError as error:
        raise CraftError(str(error)) from error
    name = data.get("name")
    code = data.get("code")
    test = data.get("test")
    if (
        not isinstance(name, str)
        or not _NAME.fullmatch(name)
        or keyword.iskeyword(name)
    ):
        raise CraftError("the craft name must be a lowercase snake_case identifier")
    if (
        not isinstance(code, str)
        or not isinstance(test, str)
        or not code.strip()
        or not test.strip()
    ):
        raise CraftError("the craft reply must include non-empty code and test strings")
    return CraftResult(name=name, code=code, test=test)


def request_craft(
    request: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> CraftResult:
    """Ask the model for a snippet proposal."""
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise CraftError("OPENAI_API_KEY is not set; the craft command needs it")
    url = chat_url(base_url or os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL)
    chosen_model = model or os.environ.get("REPOCRAFT_MODEL") or DEFAULT_MODEL
    messages = [
        {"role": "system", "content": craft_prompt()},
        {"role": "user", "content": request},
    ]
    try:
        payload = post_chat(url=url, api_key=key, model=chosen_model, messages=messages)
        content = chat_content(payload)
    except IntentError as error:
        raise CraftError(str(error)) from error
    return parse_craft(content)


def verify_craft(
    result: CraftResult, *, run_ruff: bool = True
) -> VerifiedCraft:
    """Run every deterministic gate on the proposal and report what passed."""
    checks: list[str] = []
    try:
        ast.parse(result.code)
        test_tree = ast.parse(result.test)
    except SyntaxError as error:
        raise CraftError(f"the generated code has a syntax error: {error}") from error
    checks.append("python syntax")
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(test_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported |= {
        (node.module or "").split(".")[0]
        for node in ast.walk(test_tree)
        if isinstance(node, ast.ImportFrom)
    }
    if result.name not in imported:
        raise CraftError(f"the generated test must import the module {result.name!r}")
    checks.append("test imports the module")
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        module = directory / f"{result.name}.py"
        test = directory / f"test_{result.name}.py"
        module.write_text(result.code, encoding="utf-8", newline="\n")
        test.write_text(result.test, encoding="utf-8", newline="\n")
        if run_ruff and _ruff_available():
            lint = _ruff(directory)
            if lint.returncode != 0:
                fixed = _ruff(directory, fix=True)
                if fixed.returncode != 0:
                    detail = (fixed.stdout + fixed.stderr).strip()[:400]
                    raise CraftError(f"ruff rejected the generated code: {detail}")
                result = CraftResult(
                    name=result.name,
                    code=module.read_text(encoding="utf-8"),
                    test=test.read_text(encoding="utf-8"),
                )
                checks.append("ruff (auto-fixed)")
            else:
                checks.append("ruff")
        completed = subprocess.run(
            [sys.executable, f"test_{result.name}.py"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
        )
        summary = completed.stdout + completed.stderr
        ran = _RAN_TESTS.search(summary)
        if ran is None or int(ran.group(1)) < 1:
            raise CraftError("the generated test file contains no tests")
        if completed.returncode != 0:
            raise CraftError(f"the generated tests failed:\n{summary.strip()[:400]}")
        checks.append("unit tests pass")
    return VerifiedCraft(result=result, checks=tuple(checks))


def _ruff_available() -> bool:
    return importlib.util.find_spec("ruff") is not None


def _ruff(directory: Path, *, fix: bool = False) -> subprocess.CompletedProcess[str]:
    arguments = ["-m", "ruff", "check", *(["--fix"] if fix else []), str(directory)]
    return subprocess.run(
        [sys.executable, *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
