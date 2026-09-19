"""Typed failures for production correspondence."""

from __future__ import annotations


class CorrespondenceError(RuntimeError):
    """Base class for correspondence failures."""


class PreviewRequiredError(CorrespondenceError):
    """Recipients and content must be previewed before send."""


class SendNotAuthorizedError(CorrespondenceError):
    """Message send requires an explicit authorized confirm action."""


class DraftNotFoundError(CorrespondenceError):
    """The named correspondence draft is not in the index."""


class ChannelNotConfiguredError(CorrespondenceError):
    """No live delivery channel is configured; contract delivery is local-only."""
