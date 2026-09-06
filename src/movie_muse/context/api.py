"""Public surface of ``movie_muse.context``.

Hosts and other modules must import this module, never sibling internals.
Context assembly is token/model-independent and does not invoke a model.
"""

from __future__ import annotations

from movie_muse.context.budget import (
    bundle_counts,
    fit_segments,
    segment_byte_count,
    segment_char_count,
)
from movie_muse.context.errors import (
    BranchIsolationError,
    ContextBudgetExceededError,
    ContextError,
    StaleCanonError,
    TenantIsolationError,
)
from movie_muse.context.service import ContextService
from movie_muse.context.types import (
    BoundState,
    ContextBudget,
    ContextBundle,
    ContextRequest,
    ContextSegment,
    Freshness,
    SegmentKind,
    SegmentRights,
)

__all__ = [
    "BoundState",
    "BranchIsolationError",
    "ContextBudget",
    "ContextBudgetExceededError",
    "ContextBundle",
    "ContextError",
    "ContextRequest",
    "ContextSegment",
    "ContextService",
    "Freshness",
    "SegmentKind",
    "SegmentRights",
    "StaleCanonError",
    "TenantIsolationError",
    "bundle_counts",
    "fit_segments",
    "segment_byte_count",
    "segment_char_count",
]
