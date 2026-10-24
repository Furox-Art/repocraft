# Contributing

## Setup

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

## Checks

```bash
python -m ruff check .
python -m mypy
python -m pytest --cov=repocraft --cov-branch --cov-report=term-missing --cov-fail-under=100
```

Coverage must stay at 100% of branches. The test suite includes smoke tests that
render the fixtures, install them into temporary target directories, and run the
generated projects' own gates. It also runs every generated snippet's own
`unittest` file. A change that breaks generated output will fail the suite.

## Recipes

Each recipe lives in `src/repocraft/recipes/` as `<id>.yaml` plus `<id>.py.j2`
and `test_<id>.py.j2`. The YAML is validated against
`schema/recipe.schema.json` at load time, and the id must match the file name.
Parameters are bounded integers; templates may only use the validated values.
The matcher, writer, and CLI live in `src/repocraft/recipe.py` and
`src/repocraft/cli.py`.

Add unit tests for new matching rules and recipes, and keep the generated
snippet executable with the standard library.

## Golden snapshots

When a template changes intentionally, remove the affected snapshots first
because both renderers refuse to overwrite existing files, then regenerate them:

```bash
rm -rf tests/golden/library tests/golden/cli
python -c "from pathlib import Path; from repocraft.render import render_project; from repocraft.spec import load_spec; [(render_project(load_spec(Path('tests/fixtures') / (name + '.yaml')), Path('tests/golden') / name)) for name in ('library', 'cli')]"
```

```bash
rm -rf tests/golden/recipes
python -c "from pathlib import Path; from repocraft.recipe import load_recipes, render_recipe, resolve_parameters, write_files; [(write_files(render_recipe(recipe, resolve_parameters(recipe, {})), Path('tests/golden/recipes') / recipe.id)) for recipe in load_recipes()]"
```

Review every changed golden file before committing it.

## Pull requests

- Keep each change focused and explain why it is needed.
- Add tests for behavior changes.
- Write code, comments, and documentation in English.

## Mutation testing (optional, slow)

Coverage says which lines ran; mutation testing says whether the assertions
can actually catch bugs. Two tools are supported:

```bash
# cross-platform probe (applies AST mutations, runs pytest per mutant)
python scripts/mutation_probe.py src/repocraft/yaml_loader.py tests/test_spec.py

# mutmut (Linux/WSL only; the dev extras include it)
mutmut run --paths-to-mutate src/repocraft/yaml_loader.py
```

Every surviving mutant is a missing assertion: either kill it with a test or
accept it consciously.

## Releasing

1. Bump `version` in `pyproject.toml` and `__version__` in
   `src/repocraft/__init__.py` to the same new version.
2. Run the full check suite from this file and merge to `main`.
3. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.
4. The `Publish` workflow builds the package, runs `twine check`, and uploads
   it to PyPI with the `PYPI_API_TOKEN` secret. PyPI versions are immutable,
   so never reuse a version number.
