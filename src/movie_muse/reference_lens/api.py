"""Public surface of ``movie_muse.reference_lens``.

Hosts and other modules must import this module, never sibling internals.
The lens retrieves only rights-registered sources and never claims training memory.
"""

from __future__ import annotations

from movie_muse.reference_lens.errors import (
    CitationUnresolvedError,
    LensDisabledError,
    ReferenceLensError,
    TrainingMemoryClaimError,
)
from movie_muse.reference_lens.service import ReferenceLensService
from movie_muse.reference_lens.types import (
    CounterReference,
    LensHit,
    LensSettings,
    RightsContext,
)

__all__ = [
    "CitationUnresolvedError",
    "CounterReference",
    "LensDisabledError",
    "LensHit",
    "LensSettings",
    "ReferenceLensError",
    "ReferenceLensService",
    "RightsContext",
    "TrainingMemoryClaimError",
]
