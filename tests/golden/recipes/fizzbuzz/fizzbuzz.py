"""FizzBuzz sequence."""

from __future__ import annotations


def fizzbuzz(limit: int) -> list[str]:
    """Return the FizzBuzz words for 1 through ``limit``."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    words = []
    for number in range(1, limit + 1):
        if number % 15 == 0:
            words.append("FizzBuzz")
        elif number % 3 == 0:
            words.append("Fizz")
        elif number % 5 == 0:
            words.append("Buzz")
        else:
            words.append(str(number))
    return words


def main() -> None:
    """Print the sequence configured when this file was generated."""
    print(fizzbuzz(15))


if __name__ == "__main__":
    main()
