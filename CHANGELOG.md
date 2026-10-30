# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.1] - 2026-10-29

### Added

- The determinism matrix moves to v0.3.0 and the cross-OS gate becomes
  mandatory.

### Changed

- PyPI publishing is gated on a matching tag plus a passing test suite.
- The matrix covers recipe rendering and the locale/timezone axes.

No runtime behavior changes.

## [0.4.0] - 2026-10-23

### Added

- The `craft` path: a model writes a free-form snippet and repocraft verifies
  it — python syntax, that the generated tests import the module, ruff when it
  is installed, and the generated tests themselves — before the confirmation
  prompt and the no-overwrite rules apply.

## Earlier versions

Versions 0.1.0 through 0.3.0 predate the first tagged release and were never
published. The README `Status` section records what each one added; in short:

- 0.3.0: the optional `ask` intent layer and the `fizzbuzz`, `pascal`, and
  `password` recipes.
- 0.2.0: deterministic snippet mode with four built-in recipes, strict schema
  validation, and golden snapshots.
- 0.1.0: library and CLI project scaffolds.

[0.4.1]: https://github.com/Furox-Art/repocraft/releases/tag/v0.4.1
