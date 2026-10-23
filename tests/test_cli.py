"""Tests for the command-line interface."""

from __future__ import annotations

import runpy
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from repocraft import __version__
from repocraft.cli import main
from repocraft.errors import IntentError
from repocraft.intent import Intent
from repocraft.recipe import Recipe, load_recipes

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"repocraft {__version__}\n"


def test_validate_accepts_a_valid_spec(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(FIXTURES / "library.yaml")]) == 0
    assert capsys.readouterr().out == "valid spec: example-library (library)\n"


def test_validate_reports_an_invalid_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("schema_version: 1\nproject: {}\n", encoding="utf-8")
    assert main(["validate", str(invalid)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: invalid spec:")


def test_render_writes_the_project(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "project"
    assert main(["render", str(FIXTURES / "library.yaml"), str(output)]) == 0
    assert "files to" in capsys.readouterr().out
    assert (output / "pyproject.toml").is_file()


def test_dry_run_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "planned"
    assert main(["render", str(FIXTURES / "cli.yaml"), str(output), "--dry-run"]) == 0
    printed = capsys.readouterr().out.splitlines()
    assert printed
    assert all(str(output) in line for line in printed)
    assert not output.exists()


def test_render_reports_a_refused_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "busy"
    output.mkdir()
    (output / "keep.txt").write_text("keep", encoding="utf-8")
    assert main(["render", str(FIXTURES / "library.yaml"), str(output)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "not empty" in captured.err


def test_a_command_is_required() -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([])
    assert exit_info.value.code == 2


def test_module_entry_point(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["repocraft", "--version"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("repocraft", run_name="__main__")
    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"repocraft {__version__}\n"


def test_recipes_lists_the_builtin_catalog(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["recipes"]) == 0
    expected = "".join(
        f"{recipe.id} {recipe.version}: {recipe.description}\n"
        for recipe in load_recipes()
    )
    assert capsys.readouterr().out == expected


def test_make_with_yes_writes_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "snippet"
    assert main(["make", "triangle", "-o", str(output), "--yes"]) == 0

    captured = capsys.readouterr()
    assert f"wrote {output / 'triangle.py'}" in captured.out
    assert f"wrote {output / 'test_triangle.py'}" in captured.out
    assert (output / "triangle.py").is_file()
    assert (output / "test_triangle.py").is_file()


def test_make_dry_run_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "planned"
    argv = ["make", "fibonacci", "--param", "count=3", "-o", str(output), "--dry-run"]
    assert main(argv) == 0

    printed = capsys.readouterr().out.splitlines()
    assert printed == [
        str(output / "fibonacci.py"),
        str(output / "test_fibonacci.py"),
    ]
    assert not output.exists()


def test_make_confirms_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def accept(_prompt: str = "") -> str:
        return "yes"

    monkeypatch.setattr("builtins.input", accept)
    output = tmp_path / "confirmed"
    assert main(["make", "factorial", "-o", str(output)]) == 0

    captured = capsys.readouterr().out
    assert "recipe: factorial 1.0.0" in captured
    assert "parameters: n=5" in captured
    assert "write these files?" in captured
    assert (output / "factorial.py").is_file()


def test_make_aborts_when_declined(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def decline(_prompt: str = "") -> str:
        return "n"

    monkeypatch.setattr("builtins.input", decline)
    output = tmp_path / "declined"
    assert main(["make", "fibonacci", "-o", str(output)]) == 1
    assert "aborted; no files were written" in capsys.readouterr().err
    assert not output.exists()


def test_make_requires_confirmation_without_a_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", fail)
    output = tmp_path / "no-terminal"
    assert main(["make", "fibonacci", "-o", str(output)]) == 1
    assert "confirmation required" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize(
    ("params", "fragment"),
    [
        (["count"], "expected NAME=VALUE"),
        (["=3"], "expected NAME=VALUE"),
        (["count=1", "count=2"], "more than once"),
        (["size=3"], "no parameter 'size'"),
        (["count=0"], "between 1 and 1000"),
    ],
)
def test_make_rejects_invalid_parameters(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    params: list[str],
    fragment: str,
) -> None:
    output = tmp_path / "out"
    argv = ["make", "fibonacci", "-o", str(output), "--yes"]
    for param in params:
        argv.extend(["--param", param])

    assert main(argv) == 1
    assert fragment in capsys.readouterr().err
    assert not output.exists()


def test_make_refuses_to_overwrite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "out"
    output.mkdir()
    keep = output / "fibonacci.py"
    keep.write_text("keep", encoding="utf-8")

    assert main(["make", "fibonacci", "-o", str(output), "--yes"]) == 1
    assert "refusing to overwrite" in capsys.readouterr().err
    assert keep.read_text(encoding="utf-8") == "keep"


def _install_intent(
    monkeypatch: pytest.MonkeyPatch,
    intent: Intent | None,
    error: Exception | None = None,
) -> dict[str, Any]:
    calls: dict[str, Any] = {}

    def fake(
        request: str,
        recipes: Sequence[Recipe],
        *,
        base_url: str | None,
        model: str | None,
    ) -> Intent:
        calls["request"] = request
        calls["recipes"] = recipes
        calls["base_url"] = base_url
        calls["model"] = model
        if error is not None:
            raise error
        assert intent is not None
        return intent

    monkeypatch.setattr("repocraft.cli.request_intent", fake)
    return calls


def _triangle_intent() -> Intent:
    recipe = next(entry for entry in load_recipes() if entry.id == "triangle")
    return Intent(recipe=recipe, parameters={"height": 7})


def test_ask_writes_the_validated_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = _install_intent(monkeypatch, _triangle_intent())
    output = tmp_path / "snippet"

    assert main(["ask", "a tall triangle", "-o", str(output), "--yes"]) == 0

    captured = capsys.readouterr()
    assert f"wrote {output / 'triangle.py'}" in captured.out
    assert "triangle(7)" in (output / "triangle.py").read_text(encoding="utf-8")
    assert calls["request"] == "a tall triangle"
    assert calls["base_url"] is None
    assert calls["model"] is None


def test_ask_confirms_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_intent(monkeypatch, _triangle_intent())

    def accept(_prompt: str = "") -> str:
        return "y"

    monkeypatch.setattr("builtins.input", accept)
    output = tmp_path / "confirmed"
    assert main(["ask", "a tall triangle", "-o", str(output)]) == 0
    assert "recipe: triangle 1.0.0" in capsys.readouterr().out
    assert (output / "triangle.py").is_file()


def test_ask_dry_run_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install_intent(monkeypatch, _triangle_intent())
    output = tmp_path / "planned"

    assert main(["ask", "a tall triangle", "-o", str(output), "--dry-run"]) == 0

    printed = capsys.readouterr().out.splitlines()
    assert printed == [str(output / "triangle.py"), str(output / "test_triangle.py")]
    assert not output.exists()


def test_ask_param_overrides_the_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_intent(monkeypatch, _triangle_intent())
    output = tmp_path / "snippet"

    argv = ["ask", "a tall triangle", "-o", str(output), "--yes", "--param", "height=9"]
    assert main(argv) == 0

    assert "triangle(9)" in (output / "triangle.py").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("error", "fragment"),
    [
        (IntentError("the model rejected the request: nothing fits"), "nothing fits"),
        (None, "between 1 and 100"),
    ],
)
def test_ask_reports_failures_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception | None,
    fragment: str,
) -> None:
    _install_intent(monkeypatch, _triangle_intent() if error is None else None, error)
    output = tmp_path / "out"

    argv = ["ask", "a tall triangle", "-o", str(output), "--yes"]
    if error is None:
        argv.extend(["--param", "height=0"])

    assert main(argv) == 1
    assert fragment in capsys.readouterr().err
    assert not output.exists()
