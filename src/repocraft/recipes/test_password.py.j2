"""Tests for password."""

from __future__ import annotations

import string
import unittest

import password


class PasswordTests(unittest.TestCase):
    def test_returns_the_requested_length(self) -> None:
        self.assertEqual(len(password.password(16)), 16)

    def test_uses_only_alphabet_characters(self) -> None:
        alphabet = set(string.ascii_letters + string.digits + string.punctuation)
        for character in password.password(32):
            self.assertIn(character, alphabet)

    def test_returns_a_different_password_each_time(self) -> None:
        self.assertNotEqual(password.password(16), password.password(16))

    def test_rejects_short_lengths(self) -> None:
        with self.assertRaises(ValueError):
            password.password(7)


if __name__ == "__main__":
    unittest.main()
