#!/usr/bin/env python3
"""Tiny cross-platform mutation probe.

Applies small AST mutations to one module (comparison flips, +/-1 on integer
constants, and/or swaps) and runs the given pytest selection per mutant. A
mutant the tests fail to kill is a missing assertion. The original file is
always restored.
"""

from __future__ import annotations

import ast
import copy
import subprocess
import sys
from pathlib import Path
from typing import Any

_TIMEOUT_SECONDS = 180

_FLIPS = {
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
}


def _collect_sites(tree: ast.AST) -> list[dict[str, Any]]:
    sites: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            operation = node.ops[0]
            for source, target in _FLIPS.items():
                if isinstance(operation, source):
                    sites.append({"node": node, "kind": "flip", "target": target})
                    break
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            sites.append({"node": node, "kind": "bool", "target": not node.value})
        elif isinstance(node, ast.Constant) and isinstance(node.value, int):
            sites.append({"node": node, "kind": "int", "target": node.value + 1})
        elif isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            sites.append({"node": node, "kind": "boolop", "target": ast.Or()})
        elif isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            sites.append({"node": node, "kind": "boolop", "target": ast.And()})
    return sites


def _apply(site: dict[str, Any]) -> str:
    node = site["node"]
    if site["kind"] == "flip":
        node.ops = [site["target"]()]
        return f"comparison -> {type(node.ops[0]).__name__}"
    if site["kind"] == "int":
        old = node.value
        node.value = site["target"]
        return f"constant {old} -> {node.value}"
    if site["kind"] == "bool":
        old = node.value
        node.value = site["target"]
        return f"bool {old} -> {node.value}"
    node.op = site["target"]
    return f"boolop -> {type(node.op).__name__}"


def _run_tests(test_paths: list[str]) -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q", *test_paths],
        capture_output=True,
        text=True,
        check=False,
        timeout=_TIMEOUT_SECONDS,
    )
    return "killed" if completed.returncode != 0 else "SURVIVED"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            "usage: python scripts/mutation_probe.py MODULE.py [TEST ...]",
            file=sys.stderr,
        )
        return 2
    module_path = Path(argv[1])
    test_paths = argv[2:] or ["tests"]
    original = module_path.read_bytes()
    try:
        tree = ast.parse(original.decode("utf-8"))
        sites = _collect_sites(tree)
        if not sites:
            print("no mutation sites found")
            return 0
        killed = 0
        survived = 0
        for index, site in enumerate(sites, start=1):
            mutated_tree = copy.deepcopy(tree)
            mutated_sites = _collect_sites(mutated_tree)
            target_site = mutated_sites[index - 1]
            if target_site["node"] is site["node"]:
                print("internal error: site mismatch", file=sys.stderr)
                return 2
            description = _apply(target_site)
            module_path.write_text(
                ast.unparse(mutated_tree), encoding="utf-8", newline="\n"
            )
            try:
                outcome = _run_tests(test_paths)
            except subprocess.TimeoutExpired:
                outcome = "killed (timeout)"
            location = site["node"].lineno
            print(f"#{index:03d} line {location:>4}: {description:<28} {outcome}")
            if outcome.startswith("killed"):
                killed += 1
            else:
                survived += 1
            module_path.write_bytes(original)
        total = killed + survived
        print(f"\n{total} mutants: {killed} killed, {survived} survived"
              f" (kill rate {killed / total:.0%})")
        return 0 if survived == 0 else 1
    finally:
        module_path.write_bytes(original)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
