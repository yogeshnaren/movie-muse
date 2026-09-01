"""Fail-closed errors for the revisions module."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from movie_muse.revisions.types import Merge


class RevisionError(ValueError):
    """Base error for revision/branch/checkpoint/merge/proposal commands."""


class RevisionNotFoundError(RevisionError):
    """A referenced revision, branch, checkpoint, proposal, or merge is missing."""


class StaleBaseError(RevisionError):
    """ChangeSet or proposal base is not the current branch head."""


class ProtectedBranchError(RevisionError):
    """A protected branch cannot move without an explicit allow flag."""


class ArchivedBranchError(RevisionError):
    """An archived branch cannot accept head movement."""


class CheckpointExistsError(RevisionError):
    """A checkpoint name already refers to a revision and cannot be moved."""


class StaleProposalError(RevisionError):
    """A proposal cannot be accepted or rebased against the current head."""


class RebaseError(RevisionError):
    """Proposal rebase could not apply cleanly; fail closed."""


class ReplayError(RevisionError):
    """Event replay does not reconstruct the stored branch head."""


class MergeConflictError(RevisionError):
    """Three-way merge found overlapping operations or apply failed."""

    def __init__(self, merge: Merge) -> None:
        super().__init__("merge conflicts; fail closed without moving branch head")
        self.merge = merge
