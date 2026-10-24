"""Property-based tests: mathematical invariants of the generated code and
parser robustness under arbitrary input (fuzzing), via Hypothesis."""

from __future__ import annotations

import importlib.util
import itertools
import math
import string
import sys
from types import ModuleType

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from repocraft.errors import IntentError
from repocraft.intent import parse_intent
from repocraft.recipe import Recipe, load_recipes, render_recipe, resolve_parameters

RECIPES = load_recipes()


def _recipe(recipe_id: str) -> Recipe:
    return next(entry for entry in RECIPES if entry.id == recipe_id)


def _is_prime(number: int) -> bool:
    return number > 1 and all(
        number % divisor for divisor in range(2, int(number**0.5) + 1)
    )


@pytest.fixture(scope="module")
def modules(tmp_path_factory: pytest.TempPathFactory) -> dict[str, ModuleType]:
    """Render every recipe once and import the generated module."""
    loaded: dict[str, ModuleType] = {}
    root = tmp_path_factory.mktemp("property_modules")
    for recipe in RECIPES:
        code = render_recipe(recipe, resolve_parameters(recipe, {}))[0].content
        path = root / f"{recipe.id}.py"
        path.write_text(code, encoding="utf-8")
        spec = importlib.util.spec_from_file_location(recipe.id, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[recipe.id] = module
        spec.loader.exec_module(module)
        loaded[recipe.id] = module
    return loaded


@settings(max_examples=75, deadline=None)
@given(count=st.integers(min_value=1, max_value=300))
def test_fibonacci_invariants(modules: dict[str, ModuleType], count: int) -> None:
    result = modules["fibonacci"].fibonacci(count)

    assert len(result) == count
    assert result[:2] == [0, 1][:count]
    assert all(left <= right for left, right in itertools.pairwise(result))


@settings(max_examples=75, deadline=None)
@given(n=st.integers(min_value=0, max_value=170))
def test_factorial_matches_math_factorial(modules: dict[str, ModuleType], n: int) -> None:
    assert modules["factorial"].factorial(n) == math.factorial(n)


@settings(max_examples=75, deadline=None)
@given(limit=st.integers(min_value=0, max_value=300))
def test_prime_sieve_lists_every_prime(modules: dict[str, ModuleType], limit: int) -> None:
    expected = [n for n in range(2, limit + 1) if _is_prime(n)]

    assert modules["prime_sieve"].primes_up_to(limit) == expected


@settings(max_examples=75, deadline=None)
@given(height=st.integers(min_value=1, max_value=80))
def test_triangle_rows_are_centered_odd_widths(
    modules: dict[str, ModuleType], height: int
) -> None:
    lines = modules["triangle"].triangle(height).split("\n")

    assert len(lines) == height
    for row, line in enumerate(lines):
        assert line.count("*") == 2 * row + 1
        assert line.strip() == "*" * (2 * row + 1)
    assert len(lines[-1]) == 2 * height - 1


@settings(max_examples=75, deadline=None)
@given(rows=st.integers(min_value=1, max_value=40))
def test_pascal_rows_sum_to_powers_of_two(
    modules: dict[str, ModuleType], rows: int
) -> None:
    triangle = modules["pascal"].pascal(rows)

    assert len(triangle) == rows
    for index, row in enumerate(triangle):
        assert len(row) == index + 1
        assert row[0] == 1 and row[-1] == 1
        assert sum(row) == 2**index


@settings(max_examples=75, deadline=None)
@given(limit=st.integers(min_value=1, max_value=200))
def test_fizzbuzz_words_follow_the_rules(modules: dict[str, ModuleType], limit: int) -> None:
    words = modules["fizzbuzz"].fizzbuzz(limit)

    assert len(words) == limit
    for number, word in enumerate(words, start=1):
        if number % 15 == 0:
            assert word == "FizzBuzz"
        elif number % 3 == 0:
            assert word == "Fizz"
        elif number % 5 == 0:
            assert word == "Buzz"
        else:
            assert word == str(number)


@settings(max_examples=75, deadline=None)
@given(length=st.integers(min_value=8, max_value=128))
def test_password_stays_in_the_alphabet(modules: dict[str, ModuleType], length: int) -> None:
    alphabet = set(string.ascii_letters + string.digits + string.punctuation)

    password = modules["password"].password(length)

    assert len(password) == length
    assert set(password) <= alphabet


@settings(max_examples=150, deadline=None)
@given(text=st.text())
def test_parse_intent_never_crashes_on_arbitrary_input(text: str) -> None:
    """Fuzz: arbitrary text either parses to a JSON object or fails cleanly."""
    try:
        data = parse_intent(text)
    except IntentError:
        return
    assert isinstance(data, dict)
