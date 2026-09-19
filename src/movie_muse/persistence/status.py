"""Unambiguous local/sync/backup/conflict/recovery status values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LocalSaveState(str, Enum):
    SAVED_LOCALLY = "saved_locally"
    QUEUED_FOR_SYNC = "queued_for_sync"
    SYNCED = "synced"
    BACKED_UP = "backed_up"
    CONFLICTED = "conflicted"
    RECOVERY_ONLY = "recovery_only"


@dataclass(frozen=True, slots=True)
class SaveAck:
    """Returned only after the local transaction has committed."""

    revision_id: str
    blob_digest: str
    operation_id: str
    state: LocalSaveState


@dataclass(frozen=True, slots=True)
class WorkspaceStatus:
    document_id: str | None
    head_revision_id: str | None
    save_state: LocalSaveState
    backed_up: bool
    connectivity_offline: bool
    auth_outage: bool
    subscription_outage: bool
    sync_outage: bool
    ai_outage: bool
    pending_outbox: int
    pending_inbox: int
