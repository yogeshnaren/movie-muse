"""Errors for the sync protocol."""

from __future__ import annotations


class SyncError(Exception):
    """Base error for outbox/inbox processing."""


class SyncUploadBlockedError(SyncError):
    """Network, auth, subscription, or sync outage blocks upload, not local save."""


class DuplicateEnvelopeError(SyncError):
    """An envelope with this operation_id was already accepted."""
