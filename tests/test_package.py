"""Tests for the package metadata."""

from importlib.metadata import version

from repocraft import __version__


def test_version_matches_installed_distribution() -> None:
    assert __version__ == version("repocraft")
