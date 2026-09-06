"""Errors for the local-first persistence module."""

from __future__ import annotations


class PersistenceError(Exception):
    """Base error for local store failures."""


class SaveNotAcknowledgedError(PersistenceError):
    """Raised when a save did not commit; callers must not treat it as durable."""


class CorruptStoreError(PersistenceError):
    """The embedded database failed integrity checks."""


class BackupError(PersistenceError):
    """Backup or restore could not complete."""


class MigrationError(PersistenceError):
    """Schema migration failed closed."""
