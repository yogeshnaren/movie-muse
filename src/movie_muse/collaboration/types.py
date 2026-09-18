"""Typed collaborative operations, presence, comments, and conflict views."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.schemas.api import CollaborationEvent, CollaborationRecordKind, PromotionState

FORBIDDEN_DOMAINS = frozenset(
    {"film_ir", "intent", "creative_intent", "production", "budget", "financial", "scenario"}
)


class CollabOpKind(str, Enum):
    DOCUMENT_PATCH = "document_patch"
    COMMENT = "comment"
    CURSOR = "cursor"
    PRESENCE = "presence"
    DECISION = "decision"


@dataclass(frozen=True, slots=True)
class PresenceRecord:
    actor_id: str
    device_id: str
    project_id: str
    branch_id: str
    seen_at: str
    cursor_block_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "device_id": self.device_id,
            "project_id": self.project_id,
            "branch_id": self.branch_id,
            "seen_at": self.seen_at,
            "cursor_block_id": self.cursor_block_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PresenceRecord:
        cursor = data.get("cursor_block_id")
        return cls(
            actor_id=str(data["actor_id"]),
            device_id=str(data["device_id"]),
            project_id=str(data["project_id"]),
            branch_id=str(data["branch_id"]),
            seen_at=str(data["seen_at"]),
            cursor_block_id=str(cursor) if cursor else None,
        )


@dataclass(frozen=True, slots=True)
class CollabComment:
    id: str
    project_id: str
    branch_id: str
    revision_id: str
    block_id: str
    author_actor_id: str
    text: str
    created_at: str
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "branch_id": self.branch_id,
            "revision_id": self.revision_id,
            "block_id": self.block_id,
            "author_actor_id": self.author_actor_id,
            "text": self.text,
            "created_at": self.created_at,
            "resolved": self.resolved,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CollabComment:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            branch_id=str(data["branch_id"]),
            revision_id=str(data["revision_id"]),
            block_id=str(data["block_id"]),
            author_actor_id=str(data["author_actor_id"]),
            text=str(data["text"]),
            created_at=str(data["created_at"]),
            resolved=bool(data.get("resolved", False)),
        )


@dataclass(frozen=True, slots=True)
class CollabOp:
    id: str
    kind: CollabOpKind
    project_id: str
    branch_id: str
    actor_id: str
    device_id: str
    lamport: int
    acl_epoch: int
    base_revision_id: str
    target_id: str
    payload: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "project_id": self.project_id,
            "branch_id": self.branch_id,
            "actor_id": self.actor_id,
            "device_id": self.device_id,
            "lamport": self.lamport,
            "acl_epoch": self.acl_epoch,
            "base_revision_id": self.base_revision_id,
            "target_id": self.target_id,
            "payload": dict(self.payload),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CollabOp:
        return cls(
            id=str(data["id"]),
            kind=CollabOpKind(str(data["kind"])),
            project_id=str(data["project_id"]),
            branch_id=str(data["branch_id"]),
            actor_id=str(data["actor_id"]),
            device_id=str(data["device_id"]),
            lamport=int(data["lamport"]),
            acl_epoch=int(data["acl_epoch"]),
            base_revision_id=str(data["base_revision_id"]),
            target_id=str(data["target_id"]),
            payload=dict(data.get("payload") or {}),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class ConflictView:
    left_op_id: str
    right_op_id: str
    target_id: str
    reason: str
    left_payload: dict[str, Any]
    right_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_op_id": self.left_op_id,
            "right_op_id": self.right_op_id,
            "target_id": self.target_id,
            "reason": self.reason,
            "left_payload": dict(self.left_payload),
            "right_payload": dict(self.right_payload),
        }


@dataclass(frozen=True, slots=True)
class ApplyResult:
    op: CollabOp
    conflicts: tuple[ConflictView, ...] = ()
    applied: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op.to_dict(),
            "conflicts": [item.to_dict() for item in self.conflicts],
            "applied": self.applied,
        }


__all__ = [
    "FORBIDDEN_DOMAINS",
    "ApplyResult",
    "CollabComment",
    "CollabOp",
    "CollabOpKind",
    "CollaborationEvent",
    "CollaborationRecordKind",
    "ConflictView",
    "PresenceRecord",
    "PromotionState",
]
