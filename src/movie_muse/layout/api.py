"""Public surface of ``movie_muse.layout``.

Hosts and other modules must import this module, never sibling internals.
Layout is a deterministic function of document revision + style profile +
paper profile + lock state + engine version. It never silently rewrites canon.
"""

from __future__ import annotations

from movie_muse.layout.errors import (
    LayoutEngineError,
    LayoutError,
    LockedPaginationError,
    UnknownProfileError,
)
from movie_muse.layout.locks import lock_state_from_document
from movie_muse.layout.metrics import (
    FONT_FAMILY,
    FONT_LICENSE,
    FONT_METRICS_VERSION,
    LAYOUT_ENGINE_VERSION,
)
from movie_muse.layout.profiles import A4, US_LETTER, resolve_paper_profile, resolve_style_profile
from movie_muse.layout.render import (
    CHAR_POSITION_TOLERANCE,
    LINE_INDEX_TOLERANCE,
    RASTER_PIXEL_TOLERANCE,
    ZERO_LOSS_FIELDS,
    reading_order_text,
    render_result,
)
from movie_muse.layout.service import LayoutService
from movie_muse.layout.types import (
    LayoutLine,
    LayoutObservation,
    LayoutPage,
    LayoutResult,
    LayoutTraceEvent,
    LockedPage,
    LockedScene,
    PaperProfile,
    ProductionLockState,
    StyleProfile,
)

__all__ = [
    "A4",
    "CHAR_POSITION_TOLERANCE",
    "FONT_FAMILY",
    "FONT_LICENSE",
    "FONT_METRICS_VERSION",
    "LAYOUT_ENGINE_VERSION",
    "LINE_INDEX_TOLERANCE",
    "RASTER_PIXEL_TOLERANCE",
    "US_LETTER",
    "ZERO_LOSS_FIELDS",
    "LayoutEngineError",
    "LayoutError",
    "LayoutLine",
    "LayoutObservation",
    "LayoutPage",
    "LayoutResult",
    "LayoutService",
    "LayoutTraceEvent",
    "LockedPage",
    "LockedPaginationError",
    "LockedScene",
    "PaperProfile",
    "ProductionLockState",
    "StyleProfile",
    "UnknownProfileError",
    "lock_state_from_document",
    "reading_order_text",
    "render_result",
    "resolve_paper_profile",
    "resolve_style_profile",
]
