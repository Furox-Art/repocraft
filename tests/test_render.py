"""Tests for deterministic rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from repocraft.errors import RenderError
from repocraft.render import render_project
from repocraft.spec import load_spec, validate_spec

TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures"
GOLDEN = TESTS / "golden"


def _relative_files(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


def _spec(**overrides: object) -> dict[str, Any]:
    project: dict[str, Any] = {
        "name": "floor-test",
        "package": "floor_test",
        "description": "A project used to test the Python floor.",
        "type": "library",
        "license": "MIT",
        "author": "Test Author",
    }
    project.update(overrides)
    return validate_spec({"schema_version": 1, "project": project})


@pytest.mark.parametrize("name", ["library", "cli"])
def test_render_matches_golden_snapshot(tmp_path: Path, name: str) -> None:
    spec = load_spec(FIXTURES / f"{name}.yaml")
    output = tmp_path / "project"
    render_project(spec, output)

    expected_root = GOLDEN / name
    expected = _relative_files(expected_root)
    assert _relative_files(output) == expected
    for relative in expected:
        assert (output / relative).read_bytes() == (expected_root / relative).read_bytes(), relative


@pytest.mark.parametrize("name", ["library", "cli"])
def test_render_is_byte_identical_across_runs(tmp_path: Path, name: str) -> None:
    spec = load_spec(FIXTURES / f"{name}.yaml")
    first = tmp_path / "first"
    second = tmp_path / "second"
    render_project(spec, first)
    render_project(spec, second)

    files = _relative_files(first)
    assert files == _relative_files(second)
    for relative in files:
        content = (first / relative).read_bytes()
        assert content == (second / relative).read_bytes()
        assert b"\r\n" not in content
        if content:
            assert content.endswith(b"\n"), relative


def test_dry_run_plans_without_writing(tmp_path: Path) -> None:
    spec = load_spec(FIXTURES / "library.yaml")
    planned_root = tmp_path / "planned"
    planned = render_project(spec, planned_root, dry_run=True)

    actual_root = tmp_path / "actual"
    written = render_project(spec, actual_root)
    assert [path.relative_to(planned_root) for path in planned] == [
        path.relative_to(actual_root) for path in written
    ]
    assert not planned_root.exists()


def test_existing_empty_directory_is_allowed(tmp_path: Path) -> None:
    output = tmp_path / "empty"
    output.mkdir()
    assert render_project(load_spec(FIXTURES / "library.yaml"), output)


def test_non_empty_directory_is_refused(tmp_path: Path) -> None:
    output = tmp_path / "busy"
    output.mkdir()
    keep = output / "keep.txt"
    keep.write_text("keep", encoding="utf-8")

    with pytest.raises(RenderError, match="not empty"):
        render_project(load_spec(FIXTURES / "library.yaml"), output)
    assert keep.read_text(encoding="utf-8") == "keep"


def test_file_output_path_is_refused(tmp_path: Path) -> None:
    output = tmp_path / "file"
    output.write_text("content", encoding="utf-8")

    with pytest.raises(RenderError, match="not a directory"):
        render_project(load_spec(FIXTURES / "library.yaml"), output)


def test_python_floor_controls_classifiers_and_target(tmp_path: Path) -> None:
    output = tmp_path / "project"
    render_project(_spec(python=">=3.13"), output)

    pyproject = (output / "pyproject.toml").read_text(encoding="utf-8")
    workflow = (output / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.13"' in pyproject
    assert 'target-version = "py313"' in pyproject
    assert '"Programming Language :: Python :: 3.13"' in pyproject
    assert '"Programming Language :: Python :: 3.12"' not in pyproject
    assert 'python-version: ["3.13", "3.14"]' in workflow
