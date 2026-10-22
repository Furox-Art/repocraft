"""Tests for the command-line interface."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from repocraft import __version__
from repocraft.cli import main

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
