"""Public surface of ``movie_muse.meeting_capture``.

Hosts and other modules must import this module, never sibling internals.
Recording consent is visible. Transcript edits keep provenance. Harvest
never auto-promotes candidates.
"""

from __future__ import annotations

from movie_muse.meeting_capture.errors import (
    ConsentDeniedError,
    ConsentRequiredError,
    HarvestNotOpenError,
    HarvestRequiresReviewError,
    MeetingCaptureError,
    MeetingDeletedError,
    MeetingNotFoundError,
    RetentionExpiredError,
)
from movie_muse.meeting_capture.service import MeetingCaptureService
from movie_muse.meeting_capture.types import (
    CaptureState,
    ConsentState,
    ConsentView,
    HarvestItem,
    HarvestItemState,
    MediaLink,
    MeetingSession,
    ProvenanceEntry,
    Utterance,
)

__all__ = [
    "CaptureState",
    "ConsentDeniedError",
    "ConsentRequiredError",
    "ConsentState",
    "ConsentView",
    "HarvestItem",
    "HarvestItemState",
    "HarvestNotOpenError",
    "HarvestRequiresReviewError",
    "MediaLink",
    "MeetingCaptureError",
    "MeetingCaptureService",
    "MeetingDeletedError",
    "MeetingNotFoundError",
    "MeetingSession",
    "ProvenanceEntry",
    "RetentionExpiredError",
    "Utterance",
]
