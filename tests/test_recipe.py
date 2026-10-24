"""Tests for the deterministic recipe engine."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest
import yaml

from repocraft.errors import RecipeError
from repocraft.recipe import (
    GeneratedFile,
    Recipe,
    load_recipes,
    render_recipe,
    resolve_parameters,
    select_recipe,
    write_files,
)

TESTS = Path(__file__).resolve().parent
GOLDEN = TESTS / "golden" / "recipes"
RECIPES = load_recipes()
RECIPE_IDS = [recipe.id for recipe in RECIPES]


def _recipe(recipe_id: str) -> Recipe:
    return next(recipe for recipe in RECIPES if recipe.id == recipe_id)


def _default_files(recipe_id: str) -> tuple[GeneratedFile, ...]:
    recipe = _recipe(recipe_id)
    return render_recipe(recipe, resolve_parameters(recipe, {}))


def _recipe_data(recipe_id: str = "sample") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "id": recipe_id,
        "version": "1.0.0",
        "description": "A sample recipe used by tests.",
        "triggers": ["sample"],
        "parameters": {
            "count": {
                "type": "integer",
                "default": 3,
                "minimum": 1,
                "maximum": 10,
            }
        },
    }


def _write_recipe(
    root: Path,
    data: dict[str, Any] | None = None,
    *,
    file_name: str = "sample.yaml",
    raw: str | None = None,
    code: str | None = "VALUE = [[ count ]]\n",
    test: str | None = "VALUE = 3\n",
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(_recipe_data() if data is None else data, sort_keys=False)
    (root / file_name).write_text(raw if raw is not None else text, encoding="utf-8")
    if code is not None:
        (root / "sample.py.j2").write_text(code, encoding="utf-8")
    if test is not None:
        (root / "test_sample.py.j2").write_text(test, encoding="utf-8")


def test_builtin_recipe_ids_are_sorted() -> None:
    assert RECIPE_IDS == [
        "factorial",
        "fibonacci",
        "fizzbuzz",
        "pascal",
        "password",
        "prime_sieve",
        "triangle",
    ]


@pytest.mark.parametrize(
    ("request_text", "recipe_id"),
    [
        ("triangle", "triangle"),
        ("Triangles", "triangle"),
        ("draw a triangle", "triangle"),
        ("pyramid", "triangle"),
        ("please write a fibonacci sequence", "fibonacci"),
        ("fibonaccis", "fibonacci"),
        ("factorial", "factorial"),
        ("Factorial", "factorial"),
        ("list the prime numbers", "prime_sieve"),
        ("prime sieve", "prime_sieve"),
        ("prime_sieve", "prime_sieve"),
    ],
)
def test_requests_select_one_recipe(request_text: str, recipe_id: str) -> None:
    assert select_recipe(request_text, RECIPES).id == recipe_id


def test_empty_request_is_rejected() -> None:
    with pytest.raises(RecipeError, match="request is empty"):
        select_recipe(" !!! ", RECIPES)


@pytest.mark.parametrize("request_text", ["cat", "fib"])
def test_unknown_request_is_rejected(request_text: str) -> None:
    with pytest.raises(RecipeError, match="no recipe matches"):
        select_recipe(request_text, RECIPES)


def test_ambiguous_request_lists_the_candidates() -> None:
    with pytest.raises(RecipeError) as error:
        select_recipe("triangle and fibonacci", RECIPES)
    message = str(error.value)
    assert "more than one recipe" in message
    assert "fibonacci" in message
    assert "triangle" in message


def test_numbers_in_free_text_are_rejected() -> None:
    with pytest.raises(RecipeError, match="--param"):
        select_recipe("fibonacci 10", RECIPES)


def test_defaults_are_resolved() -> None:
    assert resolve_parameters(_recipe("fibonacci"), {}) == {"count": 10}


def test_override_is_validated_and_applied() -> None:
    assert resolve_parameters(_recipe("triangle"), {"height": "7"}) == {"height": 7}


def test_parameter_bounds_are_inclusive() -> None:
    recipe = _recipe("triangle")
    assert resolve_parameters(recipe, {"height": "1"}) == {"height": 1}
    assert resolve_parameters(recipe, {"height": "100"}) == {"height": 100}


def test_unknown_parameter_is_rejected() -> None:
    with pytest.raises(RecipeError, match="no parameter 'size'"):
        resolve_parameters(_recipe("fibonacci"), {"size": "3"})


@pytest.mark.parametrize("raw", ["ten", "1.5", ""])
def test_non_integer_parameter_is_rejected(raw: str) -> None:
    with pytest.raises(RecipeError, match="must be an integer"):
        resolve_parameters(_recipe("fibonacci"), {"count": raw})


@pytest.mark.parametrize("raw", ["0", "1001"])
def test_out_of_range_parameter_is_rejected(raw: str) -> None:
    with pytest.raises(RecipeError, match="between 1 and 1000"):
        resolve_parameters(_recipe("fibonacci"), {"count": raw})


@pytest.mark.parametrize("recipe", RECIPES, ids=RECIPE_IDS)
def test_default_output_matches_golden(tmp_path: Path, recipe: Recipe) -> None:
    written = write_files(
        render_recipe(recipe, resolve_parameters(recipe, {})),
        tmp_path / "snippet",
    )
    expected_dir = GOLDEN / recipe.id
    assert sorted(path.name for path in written) == sorted(
        path.name for path in expected_dir.iterdir() if path.is_file()
    )
    for path in written:
        expected = expected_dir / path.name
        assert path.read_bytes() == expected.read_bytes(), path.name


@pytest.mark.parametrize("recipe", RECIPES, ids=RECIPE_IDS)
def test_rendering_is_byte_identical_for_the_same_inputs(recipe: Recipe) -> None:
    parameters = resolve_parameters(recipe, {})
    assert render_recipe(recipe, parameters) == render_recipe(recipe, parameters)


@pytest.mark.parametrize(
    ("recipe_id", "value"),
    [
        ("factorial", 6),
        ("fibonacci", 6),
        ("fizzbuzz", 6),
        ("pascal", 6),
        ("password", 12),
        ("prime_sieve", 6),
        ("triangle", 6),
    ],
)
def test_non_default_parameter_reaches_the_template(recipe_id: str, value: int) -> None:
    recipe = _recipe(recipe_id)
    name = recipe.parameters[0].name
    files = render_recipe(recipe, resolve_parameters(recipe, {name: str(value)}))
    assert f"({value})" in files[0].content
    assert "[[" not in files[0].content


def test_write_files_creates_a_nested_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "snippet"
    written = write_files(_default_files("fibonacci"), output)

    assert [path.name for path in written] == ["fibonacci.py", "test_fibonacci.py"]
    for path in written:
        content = path.read_bytes()
        assert b"\r\n" not in content
        assert content.endswith(b"\n")


def test_write_files_accepts_an_existing_empty_directory(tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()

    written = write_files(_default_files("fibonacci"), output)

    assert (output / "fibonacci.py").is_file()
    assert len(written) == 2


def test_recipe_records_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        _recipe("triangle").id = "changed"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        _recipe("triangle").parameters[0].name = "changed"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        GeneratedFile(name="x", content="x").name = "changed"  # type: ignore[misc]


def test_dry_run_plans_without_writing(tmp_path: Path) -> None:
    files = _default_files("fibonacci")
    output = tmp_path / "planned"
    planned = write_files(files, output, dry_run=True)

    assert [path.name for path in planned] == ["fibonacci.py", "test_fibonacci.py"]
    assert not output.exists()


def test_file_output_path_is_refused(tmp_path: Path) -> None:
    output = tmp_path / "file"
    output.write_text("content", encoding="utf-8")

    with pytest.raises(RecipeError, match="not a directory"):
        write_files(_default_files("fibonacci"), output)


def test_existing_file_is_not_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    keep = output / "fibonacci.py"
    keep.write_text("keep", encoding="utf-8")

    with pytest.raises(RecipeError, match="refusing to overwrite"):
        write_files(_default_files("fibonacci"), output)
    assert keep.read_text(encoding="utf-8") == "keep"
    assert not (output / "test_fibonacci.py").exists()


def test_custom_catalog_loads_in_sorted_order(tmp_path: Path) -> None:
    root = tmp_path / "recipes"
    _write_recipe(root)
    (root / "notes.txt").write_text("ignored", encoding="utf-8")

    recipes = load_recipes(root)

    assert [recipe.id for recipe in recipes] == ["sample"]
    assert recipes[0].triggers == ("sample",)
    assert recipes[0].parameters[0].name == "count"
    assert recipes[0].code_template == "VALUE = [[ count ]]\n"


def test_empty_catalog_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "recipes"
    root.mkdir()
    with pytest.raises(RecipeError, match="no recipes found"):
        load_recipes(root)


def test_invalid_yaml_is_reported(tmp_path: Path) -> None:
    root = tmp_path / "recipes"
    _write_recipe(root, raw="id: [\n")
    with pytest.raises(RecipeError, match="invalid YAML in recipe"):
        load_recipes(root)


def test_non_mapping_recipe_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "recipes"
    _write_recipe(root, raw="- item\n")
    with pytest.raises(RecipeError, match="mapping at the top level"):
        load_recipes(root)


def test_duplicate_key_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "recipes"
    _write_recipe(root, raw="schema_version: 1\nid: sample\nid: sample\n")
    with pytest.raises(RecipeError, match="duplicate key 'id'"):
        load_recipes(root)


def test_missing_required_field_is_reported(tmp_path: Path) -> None:
    data = _recipe_data()
    del data["id"]
    root = tmp_path / "recipes"
    _write_recipe(root, data)

    with pytest.raises(RecipeError) as error:
        load_recipes(root)
    message = str(error.value)
    assert "invalid recipe sample.yaml" in message
    assert "<root>" in message
    assert "id" in message


def test_schema_error_includes_the_field_path(tmp_path: Path) -> None:
    data = _recipe_data()
    data["triggers"] = []
    root = tmp_path / "recipes"
    _write_recipe(root, data)

    with pytest.raises(RecipeError, match="triggers"):
        load_recipes(root)


def test_multiple_schema_errors_are_sorted(tmp_path: Path) -> None:
    data = _recipe_data()
    data["description"] = ""
    data["version"] = "1"
    root = tmp_path / "recipes"
    _write_recipe(root, data)

    with pytest.raises(RecipeError) as error:
        load_recipes(root)
    message = str(error.value)
    assert message.index("description") < message.index("version")


def test_mismatched_recipe_id_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "recipes"
    _write_recipe(root, file_name="renamed.yaml")
    with pytest.raises(RecipeError, match="must match file name"):
        load_recipes(root)


def test_trigger_without_letters_or_digits_is_rejected(tmp_path: Path) -> None:
    data = _recipe_data()
    data["triggers"] = ["!!!"]
    root = tmp_path / "recipes"
    _write_recipe(root, data)
    with pytest.raises(RecipeError, match="no letters or digits"):
        load_recipes(root)


def test_parameter_minimum_above_maximum_is_rejected(tmp_path: Path) -> None:
    data = _recipe_data()
    data["parameters"]["count"]["minimum"] = 5
    data["parameters"]["count"]["maximum"] = 1
    root = tmp_path / "recipes"
    _write_recipe(root, data)
    with pytest.raises(RecipeError, match="minimum greater"):
        load_recipes(root)


def test_parameter_with_equal_bounds_is_accepted(tmp_path: Path) -> None:
    data = _recipe_data()
    data["parameters"]["count"] = {
        "type": "integer",
        "default": 3,
        "minimum": 3,
        "maximum": 3,
    }
    root = tmp_path / "recipes"
    _write_recipe(root, data)

    recipe = load_recipes(root)[0]

    assert recipe.parameters[0].minimum == 3
    assert recipe.parameters[0].maximum == 3


def test_default_outside_parameter_bounds_is_rejected(tmp_path: Path) -> None:
    data = _recipe_data()
    data["parameters"]["count"]["default"] = 20
    root = tmp_path / "recipes"
    _write_recipe(root, data)
    with pytest.raises(RecipeError, match="outside its bounds"):
        load_recipes(root)


def test_missing_code_template_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "recipes"
    _write_recipe(root, code=None)
    with pytest.raises(RecipeError, match=r"missing sample\.py\.j2"):
        load_recipes(root)


def test_missing_test_template_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "recipes"
    _write_recipe(root, test=None)
    with pytest.raises(RecipeError, match=r"missing test_sample\.py\.j2"):
        load_recipes(root)
