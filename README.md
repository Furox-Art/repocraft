# repocraft

Deterministic Python generation from validated input.

`repocraft` has two closed paths that never call a model:

- a short request such as `triangle` selects a built-in recipe and writes one
  `.py` file plus one `unittest` file;
- a small YAML spec becomes a complete Python project with packaging metadata,
  a `src/` layout, tests, lint and type-check configuration, CI, CodeQL,
  Dependabot, and a JUnit gate that rejects skipped tests.

The same input and the same `repocraft` version always produce byte-identical
output. The AI skill layer and GitHub repository creation are roadmap items.

## Status

Version 0.2.0 adds the deterministic snippet mode:

- strict JSON Schema validation for specs and recipes, plus duplicate-key
  rejection in YAML;
- four built-in recipes: `fibonacci`, `factorial`, `prime_sieve`, and
  `triangle`;
- deterministic English matching with case, accent, and suffix normalization;
- confirmation before writing, `--dry-run`, `--param`, and refusal to overwrite;
- golden snapshots and smoke tests for every generated snippet.

The project mode from 0.1.0 is unchanged: library and CLI scaffolds with
golden-tested templates, CI, CodeQL, Dependabot, and coverage/skip gates.

The AI skill layer is planned for version 2.0. This release has no model or
network dependency.

## Requirements

- Python 3.10 or newer.

## Installation

The package is not published on PyPI yet. From this checkout:

```bash
python -m pip install .
```

## Snippet mode

List the closed recipe catalog:

```bash
repocraft recipes
```

Ask for a snippet. The command shows the selected recipe, its parameters, and
the target files, then asks for confirmation:

```bash
repocraft make "triangle"       # triangle.py and test_triangle.py
repocraft make "factorial"
repocraft make "prime numbers"
```

Preview without writing anything:

```bash
repocraft make "fibonacci" --dry-run
```

Override a declared integer parameter. Free-text numbers are not interpreted:

```bash
repocraft make "fibonacci" --param count=20 --yes
```

Rules:

- only the built-in catalog is matched; unknown or ambiguous requests stop
  without writing anything;
- requests containing standalone digits are refused; use `--param` instead;
- parameters are bounded integers and are validated before rendering;
- existing target files are never overwritten;
- `--yes` skips the confirmation prompt;
- generated tests use the standard library: `python test_<recipe>.py`.

The matcher normalizes case and accents and matches word prefixes, so
`Triangles` and `draw a triangle` both select the triangle recipe. It never
calls a model.

## Project mode

Write a spec:

```yaml
schema_version: 1
project:
  name: example-cli
  package: example_cli
  description: An example command-line application.
  type: cli
  license: Apache-2.0
  author: Your Name
  version: 0.1.0
  python: ">=3.10"
  cli:
    command: example-cli
  repository:
    owner: your-user
    name: example-cli
    private: true
```

Validate it:

```bash
repocraft validate spec.yaml
```

Plan the output without writing anything:

```bash
repocraft render spec.yaml example-cli --dry-run
```

Render it:

```bash
repocraft render spec.yaml example-cli
```

`render` refuses an output directory that already contains files. It never
overwrites or merges into existing work.

### Spec fields

| Field | Required | Meaning |
|---|---|---|
| `schema_version` | yes | Must be `1`. |
| `project.name` | yes | Distribution name, lowercase letters, digits, and hyphens. |
| `project.package` | yes | Import package name, lowercase letters, digits, and underscores. |
| `project.description` | yes | One-line description, 10 to 200 characters. |
| `project.type` | yes | `library` or `cli`. |
| `project.license` | yes | `MIT` or `Apache-2.0`. |
| `project.author` | yes | Copyright holder and package author. |
| `project.version` | no | Semantic version, default `0.1.0`. |
| `project.python` | no | `>=3.10` through `>=3.14`, default `>=3.10`. |
| `project.cli.command` | for `cli` | Console script name. Forbidden for `library`. |
| `project.repository` | no | `owner`, `name`, and `private` (default `true`). |

## Determinism contract

For fixed input and a fixed `repocraft` version:

- output paths and file contents are byte-identical;
- recipe output depends only on the recipe version and validated parameters;
- recipe matching and error ordering are deterministic;
- entries are rendered in sorted order;
- files use LF line endings and a trailing newline;
- no timestamps, random identifiers, model output, or environment values are
  embedded;
- the generated MIT copyright line carries the author but no year.

The golden tests in `tests/golden/` enforce the contract file by file,
including the built-in recipe snapshots.

## Development

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
python -m ruff check .
python -m mypy
python -m pytest --cov=repocraft --cov-branch --cov-fail-under=100
```

The smoke tests install the rendered fixtures into temporary target directories
with `--no-deps --no-build-isolation`, then run the generated projects' own
quality gates. Hatchling is a dev dependency for exactly that reason.

CI runs the suite on Python 3.10 through 3.14 and rejects skipped tests through
`scripts/check_junit.py`.

## Roadmap

1. Version 2.0: a general AI skill layer that turns free-form requests into a
   strict `{recipe_id, parameters}` intent and invokes `repocraft make`. The
   model never writes code or files; unsupported requests must be rejected or
   clarified.
2. Interactive wizard for people who do not want to write project YAML.
3. Free-form natural language to a full project spec through an
   OpenAI-compatible endpoint, with a confirmation step before any file is
   written.
4. GitHub repository creation and push, private by default.
5. MCP server exposing the same validated core.

## License

MIT. See `LICENSE`.
