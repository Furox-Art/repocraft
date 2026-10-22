"""Command-line interface for repocraft."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from repocraft import __version__
from repocraft.errors import RepocraftError
from repocraft.render import render_project
from repocraft.spec import load_spec


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repocraft",
        description="Render a deterministic Python project from a validated spec.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="check a spec without writing files")
    validate.add_argument("spec", type=Path, help="path to a YAML spec")

    render = commands.add_parser("render", help="render a spec into a new directory")
    render.add_argument("spec", type=Path, help="path to a YAML spec")
    render.add_argument("output", type=Path, help="directory to create")
    render.add_argument("--dry-run", action="store_true", help="list files without writing them")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its exit status."""
    args = _build_parser().parse_args(argv)
    try:
        spec = load_spec(args.spec)
        if args.command == "validate":
            project = spec["project"]
            print(f"valid spec: {project['name']} ({project['type']})")
            return 0
        written = render_project(spec, args.output, dry_run=args.dry_run)
        if args.dry_run:
            for path in written:
                print(path)
        else:
            print(f"wrote {len(written)} files to {args.output}")
        return 0
    except RepocraftError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
