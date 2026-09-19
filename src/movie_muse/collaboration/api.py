"""Public surface of ``movie_muse.collaboration``.

Hosts and other modules must import this module, never sibling internals.
A CRDT may coordinate document/comments/cursors/presence. It cannot write
FilmIR, intent, production, or financial state.
"""

from __future__ import annotations

from movie_muse.collaboration.crdt import (
    apply_order,
    concurrent_same_target,
    conflicts_in,
    merge_ops,
)
from movie_muse.collaboration.errors import (
    BranchMismatchError,
    CollaborationError,
    ForbiddenDomainError,
    SilentLossError,
    StaleOperationError,
    UnauthorizedOperationError,
)
from movie_muse.collaboration.service import PRESENCE_TTL, CollaborationService
from movie_muse.collaboration.types import (
    FORBIDDEN_DOMAINS,
    ApplyResult,
    CollabComment,
    CollabOp,
    CollabOpKind,
    ConflictView,
    PresenceRecord,
)
from movie_muse.schemas.api import CollaborationEvent, CollaborationRecordKind, PromotionState

__all__ = [
    "FORBIDDEN_DOMAINS",
    "PRESENCE_TTL",
    "ApplyResult",
    "BranchMismatchError",
    "CollabComment",
    "CollabOp",
    "CollabOpKind",
    "CollaborationError",
    "CollaborationEvent",
    "CollaborationRecordKind",
    "CollaborationService",
    "ConflictView",
    "ForbiddenDomainError",
    "PresenceRecord",
    "PromotionState",
    "SilentLossError",
    "StaleOperationError",
    "UnauthorizedOperationError",
    "apply_order",
    "concurrent_same_target",
    "conflicts_in",
    "merge_ops",
]
