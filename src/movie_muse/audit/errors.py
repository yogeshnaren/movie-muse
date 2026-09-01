"""Fail-closed errors for the audit module."""

from __future__ import annotations


class AuditError(ValueError):
    """Base error for audit log operations."""


class AuditImmutableError(AuditError):
    """Audit records cannot be updated or deleted."""


class AuditIntegrityError(AuditError):
    """A stored audit record does not match its integrity hash."""
