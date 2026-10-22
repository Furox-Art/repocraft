"""Expected, user-facing failures."""

from __future__ import annotations


class RepocraftError(Exception):
    """A failure the CLI reports as an error instead of a traceback."""


class SpecError(RepocraftError):
    """The spec is unreadable, invalid, or contradicts itself."""


class RenderError(RepocraftError):
    """The output directory cannot be used, or rendering failed."""
