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
generated projects' own gates. A change that breaks a generated project will
fail the suite.

When a template changes intentionally, regenerate the golden snapshots:

```bash
python -c "from pathlib import Path; from repocraft.render import render_project; from repocraft.spec import load_spec; [(render_project(load_spec(Path('tests/fixtures') / (name + '.yaml')), Path('tests/golden') / name)) for name in ('library', 'cli')]"
```

Review every changed golden file before committing it.

## Pull requests

- Keep each change focused and explain why it is needed.
- Add tests for behavior changes.
- Write code, comments, and documentation in English.
