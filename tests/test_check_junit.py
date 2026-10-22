"""Tests for the JUnit report gate used by CI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_junit.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _report(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "junit.xml"
    path.write_text(f"<testsuites><testsuite>{body}</testsuite></testsuites>", encoding="utf-8")
    return path


def test_accepts_a_clean_report(tmp_path: Path) -> None:
    result = _run(str(_report(tmp_path, '<testcase name="test_one" />')))
    assert result.returncode == 0
    assert "OK: 1 test(s)" in result.stdout


def test_rejects_failures(tmp_path: Path) -> None:
    result = _run(str(_report(tmp_path, '<testcase name="test_one"><failure /></testcase>')))
    assert result.returncode == 1
    assert "1 failure(s)" in result.stdout


def test_rejects_skips(tmp_path: Path) -> None:
    result = _run(str(_report(tmp_path, '<testcase name="test_one"><skipped /></testcase>')))
    assert result.returncode == 1
    assert "1 skipped test(s)" in result.stdout


def test_rejects_errors(tmp_path: Path) -> None:
    result = _run(str(_report(tmp_path, '<testcase name="test_one"><error /></testcase>')))
    assert result.returncode == 1
    assert "1 error(s)" in result.stdout


def test_reports_a_missing_report(tmp_path: Path) -> None:
    result = _run(str(tmp_path / "missing.xml"))
    assert result.returncode == 2
    assert "cannot read" in result.stderr


def test_reports_a_malformed_report(tmp_path: Path) -> None:
    path = tmp_path / "junit.xml"
    path.write_text("<testsuite>", encoding="utf-8")
    result = _run(str(path))
    assert result.returncode == 2
    assert "cannot read" in result.stderr


def test_requires_exactly_one_argument() -> None:
    result = _run()
    assert result.returncode == 2
    assert "usage:" in result.stderr
