"""Tests for fibonacci."""

from __future__ import annotations

import unittest

import fibonacci


class FibonacciTests(unittest.TestCase):
    def test_returns_the_requested_terms(self) -> None:
        self.assertEqual(
            fibonacci.fibonacci(10),
            [0, 1, 1, 2, 3, 5, 8, 13, 21, 34],
        )

    def test_handles_one_term(self) -> None:
        self.assertEqual(fibonacci.fibonacci(1), [0])

    def test_handles_two_terms(self) -> None:
        self.assertEqual(fibonacci.fibonacci(2), [0, 1])

    def test_rejects_non_positive_counts(self) -> None:
        with self.assertRaises(ValueError):
            fibonacci.fibonacci(0)


if __name__ == "__main__":
    unittest.main()
