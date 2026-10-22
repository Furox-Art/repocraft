"""Tests for the example library function."""

from __future__ import annotations

from example_library import add


def test_add() -> None:
    assert add(2, 3) == 5
