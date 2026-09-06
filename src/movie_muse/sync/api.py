"""Public surface of ``movie_muse.sync``.

Hosts and other modules must import this module, never sibling internals.
"""

from __future__ import annotations

from movie_muse.sync.envelopes import (
    ENVELOPE_SCHEMA_VERSION,
    SyncEnvelope,
    authorization_errors,
    cross_field_integrity_errors,
)
from movie_muse.sync.errors import DuplicateEnvelopeError, SyncError, SyncUploadBlockedError
from movie_muse.sync.protocol import SyncProtocol

__all__ = [
    "ENVELOPE_SCHEMA_VERSION",
    "DuplicateEnvelopeError",
    "SyncEnvelope",
    "SyncError",
    "SyncProtocol",
    "SyncUploadBlockedError",
    "authorization_errors",
    "cross_field_integrity_errors",
]
