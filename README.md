# repocraft

[![PyPI](https://img.shields.io/pypi/v/repocraft)](https://pypi.org/project/repocraft/)

Deterministic Python generation from validated input.

`repocraft` has four paths:

- a short request such as `triangle` selects a built-in recipe and writes one
  `.py` file plus one `unittest` file;
- a small YAML spec becomes a complete Python project with packaging metadata,
  a `src/` layout, tests, lint and type-check configuration, CI, CodeQL,
  Dependabot, and a JUnit gate that rejects skipped tests;
- an optional `ask` path where a model only proposes a strict
  `{recipe, parameters}` intent, which repocraft validates before writing;
- an optional `craft` path where a model writes the snippet and repocraft
  verifies it through deterministic gates before anything is written.

The first two paths are deterministic: the same input and the same `repocraft`
version always produce byte-identical output. GitHub repository creation is a
roadmap item.

## Status

Version 0.4.1 moves the determinism matrix to v0.3.0, makes the cross-OS gate
mandatory, covers recipe rendering and the locale/timezone axes, and gates PyPI
publishing on a matching tag plus a passing test suite. No runtime behavior
changes.

Version 0.4.0 adds the `craft` path: a model writes a free-form snippet and
repocraft verifies it — python syntax, that the generated tests import the
module, ruff when it is installed, and the generated tests themselves — before
the confirmation prompt and the no-overwrite rules apply.

Version 0.3.0 adds the optional AI intent layer and three new recipes:

- `repocraft ask` sends a free-form request to an OpenAI-compatible endpoint
  and turns the reply into a strict `{recipe, parameters}` intent;
- the model never writes code or files; the intent is validated against the
  recipe catalog with the same rules as `make`;
- configuration through `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `REPOCRAFT_MODEL`,
  or `--endpoint` and `--model`;
- new recipes: `fizzbuzz`, `pascal`, and `password`.

Version 0.2.0 added the deterministic snippet mode:

- strict JSON Schema validation for specs and recipes, plus duplicate-key
  rejection in YAML;
- four built-in recipes: `fibonacci`, `factorial`, `prime_sieve`, and
  `triangle`;
- deterministic English matching with case, accent, and suffix normalization;
- confirmation before writing, `--dry-run`, `--param`, and refusal to overwrite;
- golden snapshots and smoke tests for every generated snippet.

The project mode from 0.1.0 is unchanged: library and CLI scaffolds with
golden-tested templates, CI, CodeQL, Dependabot, and coverage/skip gates.

The deterministic commands (`validate`, `render`, `recipes`, `make`) have no
model or network dependency; only `ask` uses the network.

## Requirements

- Python 3.10 or newer.

## Installation

```bash
python -m pip install repocraft
```

Or from this checkout:

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

## Ask mode (optional)

`ask` is the only command that calls a model. It turns a free-form request
into a validated intent and then reuses the snippet path end to end:

```bash
export OPENAI_API_KEY=sk-...            # required
repocraft ask "a tall triangle"          # proposes triangle with its default height
repocraft ask "first 20 fibonacci numbers" --yes
```

Rules:

- the model replies with JSON only: a recipe id and integer parameters, or
  `null` with a reason when nothing fits;
- repocraft validates the reply against the catalog; unknown recipes, invalid
  parameters, and malformed replies are rejected;
- the confirmation prompt, `--dry-run`, `--param`, and the refusal to
  overwrite behave exactly as in `make`;
- `--endpoint` selects any OpenAI-compatible base URL; `--model` or
  `REPOCRAFT_MODEL` selects the model;
- without `OPENAI_API_KEY` in the environment the command refuses to run.

## Craft mode (optional)

`craft` is the path where the model writes the code and repocraft stays in
control of quality. The model proposes a module, its source, and a unittest
file; repocraft then runs deterministic gates on the proposal before anything
is written:

```bash
export OPENAI_API_KEY=sk-...            # required
repocraft craft "binary search"          # proposes, verifies, asks, writes
```

Gates, in order:

1. python syntax of the code and the test;
2. the test must import the proposed module by name;
3. ruff on the generated files, when ruff is installed; fixable findings are
   auto-fixed first and the check is marked accordingly;
4. the generated unittest file must run and pass at least one test;
5. the confirmation prompt shows the code and every check that passed.

Rules:

- `--endpoint`, `--model`, `REPOCRAFT_MODEL`, and `OPENAI_BASE_URL` configure
  the endpoint exactly as in `ask`;
- the module name must be a lowercase snake_case identifier;
- only the standard library is allowed in the prompt, but the gates verify
  what actually runs;
- `--dry-run` lists the planned files after verification; the no-overwrite
  rule applies;
- without `OPENAI_API_KEY` in the environment the command refuses to run.

Unlike the deterministic paths, the written content depends on the model;
repocraft guarantees only that every gate passed and that you saw the code
before it was written.

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

The `ask` command adds a model, but the contract still holds: the model only
proposes an intent, and a confirmed intent renders exactly like `make`. The
`craft` command goes further — the model writes the code — so its output is
not part of the contract; its gates, the confirmation prompt, and the
no-overwrite rule are.

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

1. Interactive wizard for people who do not want to write project YAML.
2. Free-form natural language to a full project spec through an
   OpenAI-compatible endpoint, with a confirmation step before any file is
   written.
3. GitHub repository creation and push, private by default.
4. MCP server exposing the same validated core.

## Related projects

Part of the Furox scientific-computing portfolio: independently versioned projects that pair agent-facing interfaces (MCP servers and Agent Skills) with deterministic, fail-closed verification.

- [scientific-computing-system](https://github.com/Furox-Art/scientific-computing-system) — zero-dependency Python numerics with run manifests.
- [scientific-computing-system-2.0](https://github.com/Furox-Art/scientific-computing-system-2.0) — NumPy/SciPy/pandas build with replayable fit records.
- [scientific-toolkit](https://github.com/Furox-Art/scientific-toolkit) — MCP gateway over nine research tools.
- [axiomize](https://github.com/Furox-Art/axiomize) — unit-checked modeling engine with SBML, CellML and Modelica export.
- [axiomize-quantum-skills-2.0](https://github.com/Furox-Art/axiomize-quantum-skills-2.0) — modeling engine plus quantum-inspired reasoning bundle.
- [quantum-reasoning-skill](https://github.com/Furox-Art/quantum-reasoning-skill) — agent skill that keeps competing hypotheses alive.
- [plan-auditor](https://github.com/Furox-Art/plan-auditor) — evidence-based completion gate for coding agents.
- [nomosguard](https://github.com/Furox-Art/nomosguard) — deterministic security decision layer with a hash-chained ledger.
- [eq-layer](https://github.com/Furox-Art/eq-layer) — interaction-policy layer that decides how an agent speaks.
- [literature-evidence-mcp](https://github.com/Furox-Art/literature-evidence-mcp) — literature MCP server with a hash-chained evidence ledger.

## License

MIT. See `LICENSE`.
