"""Typed candidates, provenance, and promotion mapping for project memory."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.schemas.api import ProjectMemoryKind


class MemoryCandidateKind(str, Enum):
    IDEA = "idea"
    DECISION = "decision"
    QUESTION = "question"
    RESEARCH = "research"
    ASSIGNMENT = "assignment"
    REJECTED_IDEA = "rejected_idea"
    FACT = "fact"
    LINK = "link"


class MemoryStatus(str, Enum):
    CAPTURED = "captured"
    REJECTED = "rejected"
    PROMOTED = "promoted"


PROMOTABLE_KINDS: dict[MemoryCandidateKind, ProjectMemoryKind] = {
    MemoryCandidateKind.DECISION: ProjectMemoryKind.DECISION,
    MemoryCandidateKind.FACT: ProjectMemoryKind.FACT,
    MemoryCandidateKind.ASSIGNMENT: ProjectMemoryKind.ASSIGNMENT,
    MemoryCandidateKind.RESEARCH: ProjectMemoryKind.RESEARCH_NOTE,
}


@dataclass(frozen=True, slots=True)
class ProvenanceEntry:
    actor_id: str
    operation: str
    created_at: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "operation": self.operation,
            "created_at": self.created_at,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProvenanceEntry:
        return cls(
            actor_id=str(data["actor_id"]),
            operation=str(data["operation"]),
            created_at=str(data["created_at"]),
            note=str(data.get("note", "")),
        )


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    id: str
    project_id: str
    kind: MemoryCandidateKind
    summary: str
    status: MemoryStatus
    branch_id: str
    revision_id: str
    captured_by_actor_id: str
    captured_at: str
    provenance: tuple[ProvenanceEntry, ...]
    previous_id: str | None = None
    source_collaboration_event_id: str | None = None
    link_url: str | None = None
    artifact_id: str | None = None
    rights_record_id: str | None = None
    promoted_memory_id: str | None = None
    conflict_of_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "kind": self.kind.value,
            "summary": self.summary,
            "status": self.status.value,
            "branch_id": self.branch_id,
            "revision_id": self.revision_id,
            "captured_by_actor_id": self.captured_by_actor_id,
            "captured_at": self.captured_at,
            "provenance": [item.to_dict() for item in self.provenance],
            "previous_id": self.previous_id,
            "source_collaboration_event_id": self.source_collaboration_event_id,
            "link_url": self.link_url,
            "artifact_id": self.artifact_id,
            "rights_record_id": self.rights_record_id,
            "promoted_memory_id": self.promoted_memory_id,
            "conflict_of_id": self.conflict_of_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryCandidate:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            kind=MemoryCandidateKind(str(data["kind"])),
            summary=str(data["summary"]),
            status=MemoryStatus(str(data["status"])),
            branch_id=str(data["branch_id"]),
            revision_id=str(data["revision_id"]),
            captured_by_actor_id=str(data["captured_by_actor_id"]),
            captured_at=str(data["captured_at"]),
            provenance=tuple(ProvenanceEntry.from_dict(item) for item in data.get("provenance", ())),
            previous_id=str(data["previous_id"]) if data.get("previous_id") else None,
            source_collaboration_event_id=(
                str(data["source_collaboration_event_id"])
                if data.get("source_collaboration_event_id")
                else None
            ),
            link_url=str(data["link_url"]) if data.get("link_url") else None,
            artifact_id=str(data["artifact_id"]) if data.get("artifact_id") else None,
            rights_record_id=str(data["rights_record_id"]) if data.get("rights_record_id") else None,
            promoted_memory_id=(
                str(data["promoted_memory_id"]) if data.get("promoted_memory_id") else None
            ),
            conflict_of_id=str(data["conflict_of_id"]) if data.get("conflict_of_id") else None,
        )
