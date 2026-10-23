"""Command-line interface for repocraft."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from repocraft import __version__
from repocraft.errors import RecipeError, RepocraftError
from repocraft.intent import request_intent
from repocraft.recipe import (
    GeneratedFile,
    Recipe,
    load_recipes,
    render_recipe,
    resolve_parameters,
    select_recipe,
    write_files,
)
from repocraft.render import render_project
from repocraft.spec import load_spec


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repocraft",
        description="Render deterministic Python projects and snippets.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="check a spec without writing files")
    validate.add_argument("spec", type=Path, help="path to a YAML spec")

    render = commands.add_parser("render", help="render a spec into a new directory")
    render.add_argument("spec", type=Path, help="path to a YAML spec")
    render.add_argument("output", type=Path, help="directory to create")
    render.add_argument("--dry-run", action="store_true", help="list files without writing them")

    make = commands.add_parser("make", help="generate a snippet from a short request")
    make.add_argument("request", help='short request, for example "triangle"')
    make.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("."),
        help="directory to write into (default: current directory)",
    )
    make.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="override a recipe parameter; repeat for several parameters",
    )
    make.add_argument(
        "-y", "--yes", action="store_true", help="write without asking for confirmation"
    )
    make.add_argument("--dry-run", action="store_true", help="list files without writing them")

    commands.add_parser("recipes", help="list the built-in snippet recipes")

    ask = commands.add_parser(
        "ask", help="turn a free-form request into a snippet with AI"
    )
    ask.add_argument("request", help="free-form request, for example 'a tall triangle'")
    ask.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("."),
        help="directory to write into (default: current directory)",
    )
    ask.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="override an intent parameter; repeat for several parameters",
    )
    ask.add_argument(
        "-y", "--yes", action="store_true", help="write without asking for confirmation"
    )
    ask.add_argument(
        "--dry-run", action="store_true", help="list files without writing them"
    )
    ask.add_argument(
        "--endpoint",
        default=None,
        help="OpenAI-compatible base URL (default: OPENAI_BASE_URL env or the public API)",
    )
    ask.add_argument(
        "--model",
        default=None,
        help="model name (default: REPOCRAFT_MODEL env or gpt-4o-mini)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its exit status."""
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            return _validate(args)
        if args.command == "render":
            return _render(args)
        if args.command == "recipes":
            return _list_recipes()
        if args.command == "ask":
            return _ask(args)
        return _make(args)
    except RepocraftError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _validate(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    project = spec["project"]
    print(f"valid spec: {project['name']} ({project['type']})")
    return 0


def _render(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    written = render_project(spec, args.output, dry_run=args.dry_run)
    if args.dry_run:
        for path in written:
            print(path)
    else:
        print(f"wrote {len(written)} files to {args.output}")
    return 0


def _list_recipes() -> int:
    for recipe in load_recipes():
        print(f"{recipe.id} {recipe.version}: {recipe.description}")
    return 0


def _make(args: argparse.Namespace) -> int:
    recipe = select_recipe(args.request, load_recipes())
    parameters = resolve_parameters(recipe, _parse_overrides(args.param))
    return _write_snippet(recipe, parameters, args)


def _ask(args: argparse.Namespace) -> int:
    intent = request_intent(
        args.request, load_recipes(), base_url=args.endpoint, model=args.model
    )
    proposed = {name: str(value) for name, value in intent.parameters.items()}
    parameters = resolve_parameters(
        intent.recipe, proposed | _parse_overrides(args.param)
    )
    return _write_snippet(intent.recipe, parameters, args)


def _write_snippet(
    recipe: Recipe, parameters: Mapping[str, int], args: argparse.Namespace
) -> int:
    files = render_recipe(recipe, parameters)
    output = Path(args.output)
    if not args.dry_run and not args.yes:
        _confirm(recipe, parameters, files, output)
    written = write_files(files, output, dry_run=args.dry_run)
    if args.dry_run:
        for path in written:
            print(path)
    else:
        for path in written:
            print(f"wrote {path}")
    return 0


def _parse_overrides(pairs: Sequence[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for pair in pairs:
        name, separator, value = pair.partition("=")
        name = name.strip()
        if not separator or not name:
            raise RecipeError(f"invalid --param {pair!r}; expected NAME=VALUE")
        if name in overrides:
            raise RecipeError(f"--param {name!r} was given more than once")
        overrides[name] = value.strip()
    return overrides


def _confirm(
    recipe: Recipe,
    parameters: Mapping[str, int],
    files: Sequence[GeneratedFile],
    output: Path,
) -> None:
    print(f"recipe: {recipe.id} {recipe.version}")
    print(f"description: {recipe.description}")
    print("parameters: " + ", ".join(f"{name}={value}" for name, value in parameters.items()))
    for file in files:
        print(f"file: {output / file.name}")
    print("write these files? [y/N] ", end="", flush=True)
    try:
        answer = input()
    except (EOFError, OSError) as error:
        raise RecipeError(
            "confirmation required; rerun with --yes to write without prompting"
        ) from error
    if answer.strip().casefold() not in {"y", "yes"}:
        raise RecipeError("aborted; no files were written")
