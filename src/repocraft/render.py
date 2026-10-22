"""Render a validated spec into a deterministic file tree."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from repocraft.errors import RenderError

TEMPLATES = Path(__file__).resolve().parent / "templates"

# (template path, destination path, render as Jinja template)
_COMMON_FILES: tuple[tuple[str, str, bool], ...] = (
    ("common/pyproject.toml.j2", "pyproject.toml", True),
    ("common/README.md.j2", "README.md", True),
    ("common/SECURITY.md.j2", "SECURITY.md", True),
    ("common/CONTRIBUTING.md.j2", "CONTRIBUTING.md", True),
    ("common/gitignore.txt", ".gitignore", False),
    ("common/ci.yml.j2", ".github/workflows/ci.yml", True),
    ("common/codeql.yml.j2", ".github/workflows/codeql.yml", True),
    ("common/dependabot.yml", ".github/dependabot.yml", False),
    ("common/check_junit.py", "scripts/check_junit.py", False),
    ("common/init.py.j2", "src/{package}/__init__.py", True),
    ("common/py.typed", "src/{package}/py.typed", False),
    ("common/test_metadata.py.j2", "tests/test_metadata.py", True),
)

_LIBRARY_FILES: tuple[tuple[str, str, bool], ...] = (
    ("library/core.py.j2", "src/{package}/core.py", True),
    ("library/test_core.py.j2", "tests/test_core.py", True),
)

_CLI_FILES: tuple[tuple[str, str, bool], ...] = (
    ("cli/cli.py.j2", "src/{package}/cli.py", True),
    ("cli/main.py.j2", "src/{package}/__main__.py", True),
    ("cli/test_cli.py.j2", "tests/test_cli.py", True),
)

_PYTHON_VERSIONS = ("3.10", "3.11", "3.12", "3.13", "3.14")


def render_project(
    spec: dict[str, Any], out_dir: Path, *, dry_run: bool = False
) -> list[Path]:
    """Render the spec into out_dir and return the written paths.

    An existing, non-empty directory is refused rather than overwritten. With
    dry_run, nothing is written and the planned paths are returned.
    """
    if out_dir.exists():
        if not out_dir.is_dir():
            raise RenderError(f"output path {out_dir} is not a directory")
        if any(out_dir.iterdir()):
            raise RenderError(f"output directory {out_dir} is not empty")

    project: dict[str, Any] = spec["project"]
    context = _context(project)
    destinations: list[Path] = []
    for source, destination_template, is_template in _entries(project):
        destination = out_dir / destination_template.format(package=project["package"])
        destinations.append(destination)
        if dry_run:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if is_template:
            text = _environment().get_template(source).render(**context)
            destination.write_text(text, encoding="utf-8", newline="\n")
        else:
            text = (TEMPLATES / source).read_text(encoding="utf-8")
            destination.write_text(text, encoding="utf-8", newline="\n")
    return destinations


def _entries(project: dict[str, Any]) -> list[tuple[str, str, bool]]:
    entries = list(_COMMON_FILES)
    entries.extend(_CLI_FILES if project["type"] == "cli" else _LIBRARY_FILES)
    entries.append((f"licenses/{project['license']}.txt.j2", "LICENSE", True))
    return sorted(entries, key=lambda entry: entry[1])


def _context(project: dict[str, Any]) -> dict[str, Any]:
    minimum = str(project["python"]).removeprefix(">=")
    versions = [version for version in _PYTHON_VERSIONS if _at_least(version, minimum)]
    classifiers = [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        *(f"Programming Language :: Python :: {version}" for version in versions),
        "Topic :: Software Development :: Code Generators",
    ]
    return {
        **project,
        "min_python": minimum,
        "classifiers": classifiers,
        "python_matrix": "[" + ", ".join(f'"{version}"' for version in versions) + "]",
        "command": project.get("cli", {}).get("command", ""),
        "repository": project.get("repository"),
    }


def _at_least(version: str, minimum: str) -> bool:
    return tuple(int(part) for part in version.split(".")) >= tuple(
        int(part) for part in minimum.split(".")
    )


def _environment() -> Environment:
    # GitHub Actions uses ${{ ... }}; custom delimiters keep Jinja out of its way.
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
        variable_start_string="[[",
        variable_end_string="]]",
        block_start_string="[%",
        block_end_string="%]",
        comment_start_string="[#",
        comment_end_string="#]",
        trim_blocks=True,
        lstrip_blocks=True,
    )
