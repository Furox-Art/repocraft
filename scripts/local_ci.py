#!/usr/bin/env python3
"""Run the same quality gates as CI on this machine, in the same order."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _run(label: str, command: Sequence[str]) -> None:
    print(f"==> {label}: {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=REPO)
    if completed.returncode != 0:
        raise SystemExit(f"FAIL: {label} (exit {completed.returncode})")


def main() -> int:
    python = sys.executable
    with tempfile.TemporaryDirectory() as temporary:
        junit = Path(temporary) / "junit.xml"
        _run("ruff", [python, "-m", "ruff", "check", "."])
        _run("mypy", [python, "-m", "mypy"])
        _run(
            "pytest",
            [
                python,
                "-m",
                "pytest",
                "--cov=repocraft",
                "--cov-branch",
                "--cov-report=term-missing",
                "--cov-fail-under=100",
                f"--junitxml={junit}",
            ],
        )
        _run(
            "check_junit",
            [python, str(REPO / "scripts" / "check_junit.py"), str(junit)],
        )
    print("OK: all local gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
