"""Typed failures for the Google Meet adapter. Live sandbox absence is fail-closed."""

from __future__ import annotations


class GoogleMeetAdapterError(RuntimeError):
    """Base class for Google Meet adapter failures."""


class GoogleMeetSandboxUnavailableError(GoogleMeetAdapterError):
    """EXT-GOOGLE-MEET-SANDBOX stays NOT_RUN when the sandbox URL is unset."""


class GoogleMeetTokenError(GoogleMeetAdapterError):
    """Expired or revoked credentials cannot import recordings."""


class GoogleMeetWebhookError(GoogleMeetAdapterError):
    """Signed webhook validation or replay protection failed."""


class GoogleMeetScopeError(GoogleMeetAdapterError):
    """Only the declared least-privilege Google Meet scopes may be stored."""
