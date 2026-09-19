"""Revision-module domain objects that are not part of the MM-002 schema pack.

Branch, Checkpoint, Merge, and history projections live here so MM-005 does
not extend ``EVENT_TYPES`` or ChangeSet operation enums.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from movie_muse.schemas.api import ChangeSet, dataclass_to_dict


@dataclass(frozen=True, slots=True)
class Branch:
    id: str
    name: str
    head_revision_id: str
    project_id: str
    created_at: str
    protected: bool = False
    archived: bool = False

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Branch:
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            head_revision_id=str(data["head_revision_id"]),
            project_id=str(data["project_id"]),
            created_at=str(data["created_at"]),
            protected=bool(data.get("protected", False)),
            archived=bool(data.get("archived", False)),
        )


@dataclass(frozen=True, slots=True)
class Checkpoint:
    name: str
    revision_id: str
    created_at: str
    actor_id: str
    project_id: str
    id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        raw_id = data.get("id")
        return cls(
            name=str(data["name"]),
            revision_id=str(data["revision_id"]),
            created_at=str(data["created_at"]),
            actor_id=str(data["actor_id"]),
            project_id=str(data["project_id"]),
            id=str(raw_id) if raw_id is not None else None,
        )


@dataclass(frozen=True, slots=True)
class MergeConflict:
    target_id: str
    reason: str
    source_operation_ids: tuple[str, ...] = ()
    target_operation_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "reason": self.reason,
            "source_operation_ids": list(self.source_operation_ids),
            "target_operation_ids": list(self.target_operation_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MergeConflict:
        return cls(
            target_id=str(data["target_id"]),
            reason=str(data["reason"]),
            source_operation_ids=tuple(str(item) for item in data.get("source_operation_ids") or ()),
            target_operation_ids=tuple(str(item) for item in data.get("target_operation_ids") or ()),
        )


@dataclass(frozen=True, slots=True)
class MergeResolution:
    id: str
    merge_id: str
    actor_id: str
    created_at: str
    resulting_revision_id: str
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MergeResolution:
        notes = data.get("notes")
        return cls(
            id=str(data["id"]),
            merge_id=str(data["merge_id"]),
            actor_id=str(data["actor_id"]),
            created_at=str(data["created_at"]),
            resulting_revision_id=str(data["resulting_revision_id"]),
            notes=str(notes) if notes is not None else None,
        )


@dataclass(frozen=True, slots=True)
class Merge:
    id: str
    base_revision_id: str
    source_revision_id: str
    target_revision_id: str
    author_actor_id: str
    created_at: str
    conflicts: tuple[MergeConflict, ...] = ()
    resolutions: tuple[MergeResolution, ...] = ()
    resulting_revision_id: str | None = None
    status: str = "completed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "base_revision_id": self.base_revision_id,
            "source_revision_id": self.source_revision_id,
            "target_revision_id": self.target_revision_id,
            "author_actor_id": self.author_actor_id,
            "created_at": self.created_at,
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "resolutions": [resolution.to_dict() for resolution in self.resolutions],
            "resulting_revision_id": self.resulting_revision_id,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Merge:
        result = data.get("resulting_revision_id")
        return cls(
            id=str(data["id"]),
            base_revision_id=str(data["base_revision_id"]),
            source_revision_id=str(data["source_revision_id"]),
            target_revision_id=str(data["target_revision_id"]),
            author_actor_id=str(data["author_actor_id"]),
            created_at=str(data["created_at"]),
            conflicts=tuple(MergeConflict.from_dict(item) for item in data.get("conflicts") or ()),
            resolutions=tuple(
                MergeResolution.from_dict(item) for item in data.get("resolutions") or ()
            ),
            resulting_revision_id=str(result) if result is not None else None,
            status=str(data.get("status") or "completed"),
        )


@dataclass(frozen=True, slots=True)
class RevisionRecord:
    id: str
    parent_revision_id: str | None
    blob_digest: str
    created_at: str
    actor_id: str
    branch_id: str
    project_id: str
    document_id: str


@dataclass(frozen=True, slots=True)
class HistoryRecord:
    revision_id: str
    parent_revision_id: str | None
    actor_id: str
    timestamp: str
    event_ids: tuple[str, ...] = ()
    checkpoint_names: tuple[str, ...] = ()
    branch_names: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "parent_revision_id": self.parent_revision_id,
            "actor_id": self.actor_id,
            "timestamp": self.timestamp,
            "event_ids": list(self.event_ids),
            "checkpoint_names": list(self.checkpoint_names),
            "branch_names": list(self.branch_names),
        }


@dataclass(frozen=True, slots=True)
class HistoryProjection:
    branch_id: str
    branch_name: str
    head_revision_id: str
    records: tuple[HistoryRecord, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "branch_name": self.branch_name,
            "head_revision_id": self.head_revision_id,
            "records": [record.to_dict() for record in self.records],
        }


@dataclass(frozen=True, slots=True)
class DiffProjection:
    from_revision_id: str
    to_revision_id: str
    change_set: ChangeSet
    operations_text: str = field(default="")

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_revision_id": self.from_revision_id,
            "to_revision_id": self.to_revision_id,
            "change_set": self.change_set.to_dict(),
            "operations_text": self.operations_text,
        }
