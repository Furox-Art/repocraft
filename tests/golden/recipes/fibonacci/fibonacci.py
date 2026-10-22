"""Fibonacci numbers."""

from __future__ import annotations


def fibonacci(count: int) -> list[int]:
    """Return the first ``count`` Fibonacci numbers, starting with 0 and 1."""
    if count < 1:
        raise ValueError("count must be at least 1")
    numbers = [0, 1][:count]
    while len(numbers) < count:
        numbers.append(numbers[-1] + numbers[-2])
    return numbers


def main() -> None:
    """Print the sequence configured when this file was generated."""
    print(fibonacci(10))


if __name__ == "__main__":
    main()
