"""Public surface of ``movie_muse.beats``.

Hosts and other modules must import this module, never sibling internals.
Frameworks are guidance, not prescriptive truth. Manual override wins.
Named licensed templates require rights. Mapping changes invalidate analysis.
"""

from __future__ import annotations

from movie_muse.beats.errors import (
    BeatError,
    CustomFrameworkError,
    FrameworkNotFoundError,
    FrameworkRightsError,
    SlotNotFoundError,
    ThemeContrastError,
    ThemeNotFoundError,
    UnlicensedFrameworkError,
)
from movie_muse.beats.service import BeatService, builtin_themes
from movie_muse.beats.types import (
    ADVISORY_DISCLAIMER,
    LICENSED_KINDS,
    MIN_CONTRAST_RATIO,
    BeatFramework,
    BeatSlot,
    CatalogEntry,
    ColorTheme,
    ColorToken,
    CompletionView,
    FrameworkKind,
    MappingStatus,
    SlotCompletion,
    SlotFill,
    SlotMapping,
    contrast_ratio,
    relative_luminance,
)

__all__ = [
    "ADVISORY_DISCLAIMER",
    "LICENSED_KINDS",
    "MIN_CONTRAST_RATIO",
    "BeatError",
    "BeatFramework",
    "BeatService",
    "BeatSlot",
    "CatalogEntry",
    "ColorTheme",
    "ColorToken",
    "CompletionView",
    "CustomFrameworkError",
    "FrameworkKind",
    "FrameworkNotFoundError",
    "FrameworkRightsError",
    "MappingStatus",
    "SlotCompletion",
    "SlotFill",
    "SlotMapping",
    "SlotNotFoundError",
    "ThemeContrastError",
    "ThemeNotFoundError",
    "UnlicensedFrameworkError",
    "builtin_themes",
    "contrast_ratio",
    "relative_luminance",
]
