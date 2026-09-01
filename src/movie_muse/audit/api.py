"""Public surface of ``movie_muse.audit``.

Hosts and other modules must import this module, never sibling internals.
"""

from __future__ import annotations

from movie_muse.audit.errors import AuditError, AuditImmutableError, AuditIntegrityError
from movie_muse.audit.service import AuditLog
from movie_muse.audit.types import AuditRecord, PolicyDecision, compute_audit_hash

__all__ = [
    "AuditError",
    "AuditImmutableError",
    "AuditIntegrityError",
    "AuditLog",
    "AuditRecord",
    "PolicyDecision",
    "compute_audit_hash",
]
