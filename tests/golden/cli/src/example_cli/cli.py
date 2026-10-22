"""Command-line interface for example-cli."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from example_cli import __version__


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for example-cli."""
    parser = argparse.ArgumentParser(
        prog="example-cli",
        description="A generated command-line application.",
    )
    parser.add_argument("name", nargs="?", default="world", help="who to greet")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return its exit status."""
    args = build_parser().parse_args(argv)
    print(f"Hello, {args.name}!")
    return 0
