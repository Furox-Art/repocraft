"""Load, validate, and normalize a repocraft spec."""

from __future__ import annotations

import json
import keyword
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from repocraft.errors import SpecError

SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "spec.schema.json"


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys instead of keeping the last."""


def _construct_mapping(loader: Any, node: Any, deep: bool = False) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise SpecError(f"duplicate key {key!r} in spec")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def load_spec(path: Path) -> dict[str, Any]:
    """Read and validate a YAML spec file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise SpecError(f"cannot read spec {path}: {error}") from error
    return load_spec_text(text)


def load_spec_text(text: str) -> dict[str, Any]:
    """Parse and validate a YAML spec document."""
    try:
        data = yaml.load(text, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as error:
        raise SpecError(f"invalid YAML: {error}") from error
    if not isinstance(data, dict):
        raise SpecError("spec must be a mapping at the top level")
    return validate_spec(data)


def validate_spec(data: dict[str, Any]) -> dict[str, Any]:
    """Validate against the JSON Schema, then apply semantic checks and defaults."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=_error_sort_key)
    if errors:
        details = "; ".join(_describe(error) for error in errors)
        raise SpecError(f"invalid spec: {details}")
    normalized = normalize_spec(data)
    _check_semantics(normalized)
    return normalized


def normalize_spec(data: dict[str, Any]) -> dict[str, Any]:
    """Fill the documented defaults so rendering never reads an absent key."""
    project: dict[str, Any] = dict(data["project"])
    project.setdefault("version", "0.1.0")
    project.setdefault("python", ">=3.10")

    repository = project.get("repository")
    if isinstance(repository, dict):
        normalized_repository = dict(repository)
        normalized_repository.setdefault("private", True)
        project["repository"] = normalized_repository

    cli = project.get("cli")
    if isinstance(cli, dict):
        project["cli"] = dict(cli)

    return {"schema_version": data["schema_version"], "project": project}


def _error_sort_key(error: ValidationError) -> tuple[str, ...]:
    return tuple(str(part) for part in error.absolute_path)


def _describe(error: ValidationError) -> str:
    location = ".".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{location}: {error.message}"


def _check_semantics(spec: dict[str, Any]) -> None:
    package = spec["project"]["package"]
    if keyword.iskeyword(package):
        raise SpecError(f"package {package!r} is a Python keyword and cannot be imported")
