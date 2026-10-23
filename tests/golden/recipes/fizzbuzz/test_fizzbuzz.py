"""Tests for fizzbuzz."""

from __future__ import annotations

import unittest

import fizzbuzz


class FizzbuzzTests(unittest.TestCase):
    def test_returns_the_requested_words(self) -> None:
        self.assertEqual(
            fizzbuzz.fizzbuzz(15),
            [
                "1",
                "2",
                "Fizz",
                "4",
                "Buzz",
                "Fizz",
                "7",
                "8",
                "Fizz",
                "Buzz",
                "11",
                "Fizz",
                "13",
                "14",
                "FizzBuzz",
            ],
        )

    def test_handles_a_limit_of_one(self) -> None:
        self.assertEqual(fizzbuzz.fizzbuzz(1), ["1"])

    def test_marks_the_first_multiples(self) -> None:
        self.assertEqual(fizzbuzz.fizzbuzz(5)[2], "Fizz")
        self.assertEqual(fizzbuzz.fizzbuzz(5)[4], "Buzz")

    def test_rejects_non_positive_limits(self) -> None:
        with self.assertRaises(ValueError):
            fizzbuzz.fizzbuzz(0)


if __name__ == "__main__":
    unittest.main()
