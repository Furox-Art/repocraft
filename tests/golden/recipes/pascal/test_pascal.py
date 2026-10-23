"""Tests for pascal."""

from __future__ import annotations

import unittest

import pascal


class PascalTests(unittest.TestCase):
    def test_returns_the_requested_rows(self) -> None:
        rows = pascal.pascal(5)
        self.assertEqual(rows[0], [1])
        self.assertEqual(rows[1], [1, 1])
        self.assertEqual(rows[2], [1, 2, 1])
        self.assertEqual(rows[3], [1, 3, 3, 1])
        self.assertEqual(rows[4], [1, 4, 6, 4, 1])

    def test_handles_one_row(self) -> None:
        self.assertEqual(pascal.pascal(1)[0], [1])
        self.assertEqual(len(pascal.pascal(1)), 1)

    def test_handles_two_rows(self) -> None:
        self.assertEqual(pascal.pascal(2)[1], [1, 1])

    def test_rejects_non_positive_row_counts(self) -> None:
        with self.assertRaises(ValueError):
            pascal.pascal(0)


if __name__ == "__main__":
    unittest.main()
