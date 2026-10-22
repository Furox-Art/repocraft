"""Check that the runtime version matches the installed distribution."""

from importlib.metadata import version

from example_cli import __version__


def test_package_version_matches_metadata() -> None:
    assert __version__ == version("example-cli")
