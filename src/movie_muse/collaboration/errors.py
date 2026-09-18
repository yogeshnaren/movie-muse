"""Typed failures for live collaboration."""

from __future__ import annotations


class CollaborationError(RuntimeError):
    """Base class for collaboration failures."""


class StaleOperationError(CollaborationError):
    """A collaborative operation named a base revision that is no longer head."""


class UnauthorizedOperationError(CollaborationError):
    """The principal is not allowed to apply this collaborative operation."""


class ForbiddenDomainError(CollaborationError):
    """CRDT/collab ops cannot mutate FilmIR, intent, production, or financial state."""


class BranchMismatchError(CollaborationError):
    """The operation targets a branch this replica is not sharing."""


class SilentLossError(CollaborationError):
    """Concurrent edits to the same target must surface a conflict, not drop work."""
