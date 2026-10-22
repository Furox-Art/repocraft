#!/usr/bin/env python3
"""Fail when a JUnit XML report contains failures, errors, or skipped tests."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python scripts/check_junit.py JUNIT_XML", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as error:
        print(f"cannot read {path}: {error}", file=sys.stderr)
        return 2

    total = skipped = failures = errors = 0
    for case in root.iter("testcase"):
        total += 1
        skipped += case.find("skipped") is not None
        failures += case.find("failure") is not None
        errors += case.find("error") is not None

    if failures or errors:
        print(f"FAIL: {failures} failure(s), {errors} error(s) in {total} test(s)")
        return 1
    if skipped:
        print(f"FAIL: {skipped} skipped test(s); skips are not allowed")
        return 1
    print(f"OK: {total} test(s), no failures, errors, or skips")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
