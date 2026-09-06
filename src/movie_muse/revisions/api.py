"""Public surface of ``movie_muse.revisions``.

Hosts and other modules must import this module, never sibling internals.
"""

from __future__ import annotations

from movie_muse.revisions.errors import (
    ArchivedBranchError,
    CheckpointExistsError,
    MergeConflictError,
    ProtectedBranchError,
    RebaseError,
    ReplayError,
    RevisionError,
    RevisionNotFoundError,
    StaleBaseError,
    StaleProposalError,
)
from movie_muse.revisions.events import EVENT_TYPE, make_project_event
from movie_muse.revisions.merge import (
    compose_operations,
    content_equal,
    diff_against_base,
    effective_operations,
    overlapping_targets,
    snapshot_for_diff,
)
from movie_muse.revisions.projection import (
    render_diff_text,
    render_history_html,
    render_history_text,
)
from movie_muse.revisions.service import DEFAULT_BRANCH_NAME, DEFAULT_DEVICE_ID, RevisionService
from movie_muse.revisions.types import (
    Branch,
    Checkpoint,
    DiffProjection,
    HistoryProjection,
    HistoryRecord,
    Merge,
    MergeConflict,
    MergeResolution,
    RevisionRecord,
)

__all__ = [
    "DEFAULT_BRANCH_NAME",
    "DEFAULT_DEVICE_ID",
    "EVENT_TYPE",
    "ArchivedBranchError",
    "Branch",
    "Checkpoint",
    "CheckpointExistsError",
    "DiffProjection",
    "HistoryProjection",
    "HistoryRecord",
    "Merge",
    "MergeConflict",
    "MergeConflictError",
    "MergeResolution",
    "ProtectedBranchError",
    "RebaseError",
    "ReplayError",
    "RevisionError",
    "RevisionNotFoundError",
    "RevisionRecord",
    "RevisionService",
    "StaleBaseError",
    "StaleProposalError",
    "compose_operations",
    "content_equal",
    "diff_against_base",
    "effective_operations",
    "make_project_event",
    "overlapping_targets",
    "render_diff_text",
    "render_history_html",
    "render_history_text",
    "snapshot_for_diff",
]
