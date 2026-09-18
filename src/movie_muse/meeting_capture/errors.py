"""Typed failures for meeting capture."""

from __future__ import annotations


class MeetingCaptureError(RuntimeError):
    """Base class for meeting-capture failures."""


class MeetingNotFoundError(MeetingCaptureError):
    """The named meeting session is not in the index."""


class ConsentRequiredError(MeetingCaptureError):
    """Recording or import requires visible granted consent."""


class ConsentDeniedError(MeetingCaptureError):
    """Consent was denied or withdrawn."""


class MeetingDeletedError(MeetingCaptureError):
    """The meeting was deleted and is no longer readable."""


class RetentionExpiredError(MeetingCaptureError):
    """Retention elapsed; the transcript is no longer available."""


class HarvestRequiresReviewError(MeetingCaptureError):
    """Meeting candidates cannot auto-promote; explicit harvest review is required."""


class HarvestNotOpenError(MeetingCaptureError):
    """Promote/discard through harvest requires an open harvest review."""
