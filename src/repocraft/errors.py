"""Expected, user-facing failures."""

from __future__ import annotations


class RepocraftError(Exception):
    """A failure the CLI reports as an error instead of a traceback."""


class SpecError(RepocraftError):
    """The spec is unreadable, invalid, or contradicts itself."""


class RenderError(RepocraftError):
    """The output directory cannot be used, or rendering failed."""


class RecipeError(RepocraftError):
    """A recipe is invalid, or a request cannot be matched unambiguously."""


class IntentError(RepocraftError):
    """The AI intent layer is unusable, or returned an unusable intent."""
