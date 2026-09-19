"""Public surface of ``movie_muse.security``.

Hosts and other modules must import this module, never sibling internals.
"""

from __future__ import annotations

from movie_muse.security.crypto import derive_workspace_key, seal, unseal
from movie_muse.security.errors import (
    IntegrityError,
    KeyUnavailableError,
    OpenHighSeverityError,
    SecurityError,
)
from movie_muse.security.index import INDEX_META_KEY
from movie_muse.security.plane import ControlPlane
from movie_muse.security.service import SecurityService
from movie_muse.security.types import (
    CLASSIFICATION_RANKS,
    REMOTE_MAX,
    FindingSeverity,
    FindingStatus,
    SealedBlob,
    ThreatFinding,
)

__all__ = [
    "CLASSIFICATION_RANKS",
    "INDEX_META_KEY",
    "REMOTE_MAX",
    "ControlPlane",
    "FindingSeverity",
    "FindingStatus",
    "IntegrityError",
    "KeyUnavailableError",
    "OpenHighSeverityError",
    "SealedBlob",
    "SecurityError",
    "SecurityService",
    "ThreatFinding",
    "derive_workspace_key",
    "seal",
    "unseal",
]
