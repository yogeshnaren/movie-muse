"""Public surface of ``movie_muse.persistence``.

Hosts and other modules must import this module, never sibling internals.
"""

from __future__ import annotations

from movie_muse.persistence.backup import create_backup, restore_backup
from movie_muse.persistence.canonical import digest_payload, utc_now
from movie_muse.persistence.errors import (
    BackupError,
    CorruptStoreError,
    MigrationError,
    PersistenceError,
    SaveNotAcknowledgedError,
)
from movie_muse.persistence.migrations import CURRENT_SCHEMA_VERSION
from movie_muse.persistence.recovery import recover_if_corrupt
from movie_muse.persistence.status import LocalSaveState, SaveAck, WorkspaceStatus
from movie_muse.persistence.store import LocalStore
from movie_muse.persistence.workspace import LocalWorkspace

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "BackupError",
    "CorruptStoreError",
    "LocalSaveState",
    "LocalStore",
    "LocalWorkspace",
    "MigrationError",
    "PersistenceError",
    "SaveAck",
    "SaveNotAcknowledgedError",
    "WorkspaceStatus",
    "create_backup",
    "digest_payload",
    "recover_if_corrupt",
    "restore_backup",
    "utc_now",
]
