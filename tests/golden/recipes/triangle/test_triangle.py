"""Tests for triangle."""

from __future__ import annotations

import unittest

import triangle


class TriangleTests(unittest.TestCase):
    def test_draws_a_centered_triangle(self) -> None:
        self.assertEqual(triangle.triangle(3), "  *\n ***\n*****")

    def test_draws_a_single_row(self) -> None:
        self.assertEqual(triangle.triangle(1), "*")

    def test_leaves_no_trailing_whitespace(self) -> None:
        for line in triangle.triangle(6).splitlines():
            self.assertEqual(line, line.rstrip())

    def test_rejects_non_positive_heights(self) -> None:
        with self.assertRaises(ValueError):
            triangle.triangle(0)


if __name__ == "__main__":
    unittest.main()
