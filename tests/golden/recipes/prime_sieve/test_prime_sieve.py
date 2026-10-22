"""Tests for prime_sieve."""

from __future__ import annotations

import unittest

import prime_sieve


class PrimeSieveTests(unittest.TestCase):
    def test_returns_the_primes_up_to_the_limit(self) -> None:
        self.assertEqual(
            prime_sieve.primes_up_to(30),
            [2, 3, 5, 7, 11, 13, 17, 19, 23, 29],
        )

    def test_returns_no_primes_below_two(self) -> None:
        self.assertEqual(prime_sieve.primes_up_to(0), [])
        self.assertEqual(prime_sieve.primes_up_to(1), [])

    def test_includes_the_limit_when_it_is_prime(self) -> None:
        self.assertEqual(prime_sieve.primes_up_to(2), [2])

    def test_rejects_negative_limits(self) -> None:
        with self.assertRaises(ValueError):
            prime_sieve.primes_up_to(-1)


if __name__ == "__main__":
    unittest.main()
