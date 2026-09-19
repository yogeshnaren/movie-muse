"""Typed failures for beat frameworks."""

from __future__ import annotations


class BeatError(RuntimeError):
    """Base class for beat-framework failures."""


class FrameworkNotFoundError(BeatError):
    """The named framework is not in the index."""


class SlotNotFoundError(BeatError):
    """The named story-function slot is not on the framework."""


class MappingNotFoundError(BeatError):
    """The named mapping is not on the framework."""


class ThemeNotFoundError(BeatError):
    """The named color theme is not registered."""


class ThemeContrastError(BeatError):
    """A theme token fails the accessible contrast floor."""


class UnlicensedFrameworkError(BeatError):
    """A named licensed template was requested without permitted rights."""


class FrameworkRightsError(BeatError):
    """The registered source does not permit using this named template."""


class CustomFrameworkError(BeatError):
    """Custom framework slots are missing or invalid."""
