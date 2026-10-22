"""Tests for loading, validating, and normalizing specs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from repocraft.errors import SpecError
from repocraft.spec import load_spec, load_spec_text, validate_spec

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _valid_project(**overrides: object) -> dict[str, Any]:
    project: dict[str, Any] = {
        "name": "sample-project",
        "package": "sample_project",
        "description": "A sample project used by the tests.",
        "type": "library",
        "license": "MIT",
        "author": "Test Author",
    }
    project.update(overrides)
    return {"schema_version": 1, "project": project}


def test_load_library_spec_applies_defaults() -> None:
    spec = load_spec(FIXTURES / "library.yaml")
    project = spec["project"]
    assert project["version"] == "0.1.0"
    assert project["python"] == ">=3.10"
    assert "repository" not in project


def test_load_cli_spec_keeps_explicit_values() -> None:
    spec = load_spec(FIXTURES / "cli.yaml")
    project = spec["project"]
    assert project["version"] == "1.2.3"
    assert project["cli"] == {"command": "example-cli"}
    assert project["repository"] == {
        "owner": "example-owner",
        "name": "example-cli",
        "private": False,
    }


def test_repository_defaults_to_private() -> None:
    spec = validate_spec(_valid_project(repository={"owner": "owner", "name": "repo"}))
    assert spec["project"]["repository"]["private"] is True


def test_missing_file_is_reported() -> None:
    with pytest.raises(SpecError, match="cannot read spec"):
        load_spec(FIXTURES / "does-not-exist.yaml")


def test_invalid_yaml_is_reported() -> None:
    with pytest.raises(SpecError, match="invalid YAML"):
        load_spec_text("schema_version: [1\n")


def test_non_mapping_document_is_rejected() -> None:
    with pytest.raises(SpecError, match="mapping at the top level"):
        load_spec_text("- schema_version\n")


def test_duplicate_key_is_rejected() -> None:
    text = "schema_version: 1\nschema_version: 1\nproject: {}\n"
    with pytest.raises(SpecError, match="duplicate key 'schema_version'"):
        load_spec_text(text)


@pytest.mark.parametrize(
    ("data", "fragment"),
    [
        ({"schema_version": 2, "project": _valid_project()["project"]}, "schema_version"),
        ({"schema_version": 1}, "project"),
        (_valid_project(name="Bad Name"), "project.name"),
        (_valid_project(description="short"), "project.description"),
        (_valid_project(type="web"), "project.type"),
        (_valid_project(python=">=3.9"), "project.python"),
        (_valid_project(version="1.0"), "project.version"),
        (_valid_project(author=""), "project.author"),
        (_valid_project(extra=True), "extra"),
        (_valid_project(type="library", cli={"command": "tool"}), "project"),
        (_valid_project(type="cli"), "project"),
        (_valid_project(repository={"owner": "owner"}), "project.repository"),
        (
            _valid_project(repository={"owner": "owner", "name": "repo", "private": "yes"}),
            "project.repository.private",
        ),
    ],
)
def test_schema_violations_are_reported(data: dict[str, Any], fragment: str) -> None:
    with pytest.raises(SpecError) as error:
        validate_spec(data)
    assert fragment in str(error.value)


def test_multiple_errors_are_sorted_by_path() -> None:
    data = _valid_project(name="Bad", package="Bad", description="short")
    with pytest.raises(SpecError) as error:
        validate_spec(data)
    message = str(error.value)
    assert message.index("project.description") < message.index("project.name")


def test_python_keyword_package_is_rejected() -> None:
    with pytest.raises(SpecError, match="Python keyword"):
        validate_spec(_valid_project(package="class"))
