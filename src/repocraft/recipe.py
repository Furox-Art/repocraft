"""Match short requests to deterministic snippet recipes."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from jsonschema import Draft202012Validator

from repocraft.errors import RecipeError
from repocraft.render import template_environment

if TYPE_CHECKING:
    from importlib.abc import Traversable

_INTEGER = re.compile(r"-?[0-9]+")


class _RecipeYamlLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys instead of keeping the last."""


def _construct_mapping(loader: Any, node: Any, deep: bool = False) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise RecipeError(f"duplicate key {key!r} in recipe")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_RecipeYamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


@dataclass(frozen=True)
class Parameter:
    """One validated integer parameter of a recipe."""

    name: str
    minimum: int
    maximum: int
    default: int


@dataclass(frozen=True)
class Recipe:
    """A validated recipe with its templates already loaded."""

    id: str
    version: str
    description: str
    triggers: tuple[str, ...]
    parameters: tuple[Parameter, ...]
    code_template: str
    test_template: str


@dataclass(frozen=True)
class GeneratedFile:
    """One generated file, named relative to the output directory."""

    name: str
    content: str


def load_recipes(base: Traversable | None = None) -> tuple[Recipe, ...]:
    """Load and validate every recipe, sorted by file name."""
    root = base if base is not None else resources.files("repocraft").joinpath("recipes")
    schema = _load_schema()
    entries = sorted(root.iterdir(), key=lambda entry: entry.name)
    recipes = tuple(
        _load_recipe(root, entry, schema)
        for entry in entries
        if entry.name.endswith(".yaml")
    )
    if not recipes:
        raise RecipeError(f"no recipes found in {root}")
    return recipes


def select_recipe(request: str, recipes: Sequence[Recipe]) -> Recipe:
    """Return the single recipe matching request; never guesses between matches."""
    tokens = _normalize(request).split()
    if not tokens:
        raise RecipeError("request is empty; run 'repocraft recipes' to list available recipes")
    if any(token.isascii() and token.isdigit() for token in tokens):
        raise RecipeError(
            "numbers in free text are not interpreted; pass --param name=value instead"
        )
    matches = [
        recipe
        for recipe in recipes
        if any(_matches(tokens, trigger) for trigger in recipe.triggers)
    ]
    if not matches:
        raise RecipeError(
            f"no recipe matches {request!r}; run 'repocraft recipes' to list available recipes"
        )
    if len(matches) > 1:
        listed = ", ".join(recipe.id for recipe in matches)
        raise RecipeError(f"request matches more than one recipe ({listed}); name exactly one")
    return matches[0]


def resolve_parameters(recipe: Recipe, overrides: Mapping[str, str]) -> dict[str, int]:
    """Return recipe defaults with validated command-line overrides applied."""
    by_name = {parameter.name: parameter for parameter in recipe.parameters}
    values = {parameter.name: parameter.default for parameter in recipe.parameters}
    for name in sorted(overrides):
        parameter = by_name.get(name)
        if parameter is None:
            raise RecipeError(f"recipe {recipe.id!r} has no parameter {name!r}")
        raw = overrides[name].strip()
        if not _INTEGER.fullmatch(raw):
            raise RecipeError(f"parameter {name!r} must be an integer")
        value = int(raw)
        if not parameter.minimum <= value <= parameter.maximum:
            raise RecipeError(
                f"parameter {name!r} must be between "
                f"{parameter.minimum} and {parameter.maximum}"
            )
        values[name] = value
    return values


def render_recipe(
    recipe: Recipe, parameters: Mapping[str, int]
) -> tuple[GeneratedFile, ...]:
    """Render the recipe's code and test files from validated parameters."""
    environment = template_environment()
    context = dict(parameters)
    return (
        GeneratedFile(
            name=f"{recipe.id}.py",
            content=environment.from_string(recipe.code_template).render(context),
        ),
        GeneratedFile(
            name=f"test_{recipe.id}.py",
            content=environment.from_string(recipe.test_template).render(context),
        ),
    )


def write_files(
    files: Sequence[GeneratedFile], output: Path, *, dry_run: bool = False
) -> tuple[Path, ...]:
    """Write generated files and refuse to overwrite existing paths."""
    if output.exists() and not output.is_dir():
        raise RecipeError(f"output path {output} is not a directory")
    targets = tuple(output / file.name for file in files)
    existing = [target for target in targets if target.exists()]
    if existing:
        raise RecipeError(f"refusing to overwrite {existing[0]}")
    if dry_run:
        return targets
    output.mkdir(parents=True, exist_ok=True)
    for file, target in zip(files, targets, strict=True):
        target.write_text(file.content, encoding="utf-8", newline="\n")
    return targets


def _load_schema() -> dict[str, Any]:
    text = (
        resources.files("repocraft")
        .joinpath("schema")
        .joinpath("recipe.schema.json")
        .read_text(encoding="utf-8")
    )
    schema: dict[str, Any] = json.loads(text)
    return schema


def _load_recipe(root: Traversable, entry: Traversable, schema: dict[str, Any]) -> Recipe:
    try:
        data = yaml.load(entry.read_text(encoding="utf-8"), Loader=_RecipeYamlLoader)
    except yaml.YAMLError as error:
        raise RecipeError(f"invalid YAML in recipe {entry.name}: {error}") from error
    if not isinstance(data, dict):
        raise RecipeError(f"recipe {entry.name} must be a mapping at the top level")
    details = _format_errors(Draft202012Validator(schema), data)
    if details:
        raise RecipeError(f"invalid recipe {entry.name}: {details}")
    recipe_id: str = data["id"]
    if entry.name != f"{recipe_id}.yaml":
        raise RecipeError(f"recipe id {recipe_id!r} must match file name {entry.name!r}")
    triggers = tuple(str(trigger) for trigger in data["triggers"])
    for trigger in triggers:
        if not _normalize(trigger):
            raise RecipeError(f"recipe {recipe_id!r} has a trigger with no letters or digits")
    return Recipe(
        id=recipe_id,
        version=data["version"],
        description=data["description"],
        triggers=triggers,
        parameters=_parse_parameters(data["parameters"]),
        code_template=_template(root, recipe_id, f"{recipe_id}.py.j2"),
        test_template=_template(root, recipe_id, f"test_{recipe_id}.py.j2"),
    )


def _parse_parameters(
    raw: dict[str, dict[str, Any]],
) -> tuple[Parameter, ...]:
    parameters: list[Parameter] = []
    for name in sorted(raw):
        definition = raw[name]
        minimum: int = definition["minimum"]
        maximum: int = definition["maximum"]
        default: int = definition["default"]
        if minimum > maximum:
            raise RecipeError(f"parameter {name!r} has a minimum greater than its maximum")
        if not minimum <= default <= maximum:
            raise RecipeError(f"parameter {name!r} default is outside its bounds")
        parameters.append(
            Parameter(name=name, minimum=minimum, maximum=maximum, default=default)
        )
    return tuple(parameters)


def _template(root: Traversable, recipe_id: str, name: str) -> str:
    template = root.joinpath(name)
    if not template.is_file():
        raise RecipeError(f"recipe {recipe_id!r} is missing {name}")
    return template.read_text(encoding="utf-8")


def _format_errors(validator: Draft202012Validator, data: Any) -> str:
    errors = sorted(
        validator.iter_errors(data),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    return "; ".join(
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in errors
    )


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[^\W_]+", unaccented.casefold()))


def _matches(tokens: Sequence[str], trigger: str) -> bool:
    expected = _normalize(trigger).split()
    size = len(expected)
    if size > len(tokens):
        return False
    for start in range(len(tokens) - size + 1):
        window = tokens[start : start + size]
        if all(
            token.startswith(part)
            for token, part in zip(window, expected, strict=True)
        ):
            return True
    return False
