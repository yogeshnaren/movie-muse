"""Public surface of ``movie_muse.production_revisions``.

Overlays on LayoutResult. Unlock/repagination emits ProductionRequirementConfirmed.
Hosts import this module, never sibling internals.
"""

from __future__ import annotations

from movie_muse.production_revisions.errors import (
    ExportError,
    ProductionRevisionError,
    SidesError,
    UnlockDeniedError,
)
from movie_muse.production_revisions.events import EVENT_TYPE, make_unlock_event
from movie_muse.production_revisions.service import (
    ChangedPages,
    ProductionRevisionService,
    SidesPacket,
)

__all__ = [
    "EVENT_TYPE",
    "ChangedPages",
    "ExportError",
    "ProductionRevisionError",
    "ProductionRevisionService",
    "SidesError",
    "SidesPacket",
    "UnlockDeniedError",
    "make_unlock_event",
]
