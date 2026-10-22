"""Render the fixtures and run each generated project's own quality gates."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from repocraft.recipe import (
    Recipe,
    load_recipes,
    render_recipe,
    resolve_parameters,
    write_files,
)
from repocraft.render import render_project
from repocraft.spec import load_spec

FIXTURES = Path(__file__).resolve().parent / "fixtures"
RECIPES = load_recipes()


def _run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, (
        f"command failed: {command}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )


@pytest.mark.parametrize(
    ("fixture", "package"),
    [("library", "example_library"), ("cli", "example_cli")],
)
def test_generated_project_passes_its_own_gates(
    tmp_path: Path, fixture: str, package: str
) -> None:
    project = tmp_path / "project"
    render_project(load_spec(FIXTURES / f"{fixture}.yaml"), project)

    site = tmp_path / "site"
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            "--no-deps",
            "--no-build-isolation",
            "--target",
            str(site),
            str(project),
        ],
        cwd=tmp_path,
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(site), str(project / "src")])
    _run([sys.executable, "-m", "ruff", "check", "."], cwd=project, env=env)
    _run([sys.executable, "-m", "mypy"], cwd=project, env=env)
    _run([sys.executable, "-m", "pytest", "--junitxml=junit.xml"], cwd=project, env=env)
    _run([sys.executable, "scripts/check_junit.py", "junit.xml"], cwd=project, env=env)


@pytest.mark.parametrize("recipe", RECIPES, ids=[recipe.id for recipe in RECIPES])
def test_generated_snippet_passes_its_own_tests(tmp_path: Path, recipe: Recipe) -> None:
    write_files(render_recipe(recipe, resolve_parameters(recipe, {})), tmp_path)

    _run([sys.executable, f"test_{recipe.id}.py"], cwd=tmp_path)
    _run([sys.executable, f"{recipe.id}.py"], cwd=tmp_path)
