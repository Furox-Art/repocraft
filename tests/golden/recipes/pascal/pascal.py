"""Pascal's triangle."""

from __future__ import annotations


def pascal(rows: int) -> list[list[int]]:
    """Return Pascal's triangle with ``rows`` rows."""
    if rows < 1:
        raise ValueError("rows must be at least 1")
    triangle: list[list[int]] = []
    row = [1]
    for _ in range(rows):
        triangle.append(row)
        row = [1, *(a + b for a, b in zip(row, row[1:])), 1]
    return triangle


def main() -> None:
    """Print the triangle configured when this file was generated."""
    for row in pascal(5):
        print(" ".join(str(value) for value in row))


if __name__ == "__main__":
    main()
