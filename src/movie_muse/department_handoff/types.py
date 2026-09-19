"""Department packets, craft decisions, notices, and assignments."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.breakdown.api import BreakdownElement
from movie_muse.schemas.api import ProjectEvent


class CraftAction(str, Enum):
    CONFIRM = "confirm"
    CORRECT = "correct"
    ADD_ASSUMPTION = "add_assumption"
    ASK_DIRECTOR = "ask_director"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class CraftDecision:
    id: str
    project_id: str
    breakdown_id: str
    element_id: str
    department: str
    action: CraftAction
    actor_id: str
    note: str
    created_at: str
    event_id: str | None = None
    acknowledged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "breakdown_id": self.breakdown_id,
            "element_id": self.element_id,
            "department": self.department,
            "action": self.action.value,
            "actor_id": self.actor_id,
            "note": self.note,
            "created_at": self.created_at,
            "event_id": self.event_id,
            "acknowledged": self.acknowledged,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CraftDecision:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            breakdown_id=str(data["breakdown_id"]),
            element_id=str(data["element_id"]),
            department=str(data["department"]),
            action=CraftAction(str(data["action"])),
            actor_id=str(data["actor_id"]),
            note=str(data.get("note", "")),
            created_at=str(data["created_at"]),
            event_id=str(data["event_id"]) if data.get("event_id") else None,
            acknowledged=bool(data.get("acknowledged", False)),
        )


@dataclass(frozen=True, slots=True)
class ChangeNotice:
    id: str
    project_id: str
    breakdown_id: str
    department: str
    source_revision_id: str
    element_ids: tuple[str, ...]
    created_at: str
    created_by_actor_id: str
    acknowledged_by_actor_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "breakdown_id": self.breakdown_id,
            "department": self.department,
            "source_revision_id": self.source_revision_id,
            "element_ids": list(self.element_ids),
            "created_at": self.created_at,
            "created_by_actor_id": self.created_by_actor_id,
            "acknowledged_by_actor_id": self.acknowledged_by_actor_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChangeNotice:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            breakdown_id=str(data["breakdown_id"]),
            department=str(data["department"]),
            source_revision_id=str(data["source_revision_id"]),
            element_ids=tuple(str(item) for item in data.get("element_ids", ())),
            created_at=str(data["created_at"]),
            created_by_actor_id=str(data["created_by_actor_id"]),
            acknowledged_by_actor_id=(
                str(data["acknowledged_by_actor_id"])
                if data.get("acknowledged_by_actor_id")
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class Assignment:
    id: str
    project_id: str
    breakdown_id: str
    element_id: str
    department: str
    assignee_actor_id: str
    created_at: str
    created_by_actor_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "breakdown_id": self.breakdown_id,
            "element_id": self.element_id,
            "department": self.department,
            "assignee_actor_id": self.assignee_actor_id,
            "created_at": self.created_at,
            "created_by_actor_id": self.created_by_actor_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Assignment:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            breakdown_id=str(data["breakdown_id"]),
            element_id=str(data["element_id"]),
            department=str(data["department"]),
            assignee_actor_id=str(data["assignee_actor_id"]),
            created_at=str(data["created_at"]),
            created_by_actor_id=str(data["created_by_actor_id"]),
        )


@dataclass(frozen=True, slots=True)
class DepartmentPacket:
    id: str
    project_id: str
    breakdown_id: str
    department: str
    source_revision_id: str
    elements: tuple[BreakdownElement, ...]
    decisions: tuple[CraftDecision, ...]
    notices: tuple[ChangeNotice, ...]
    assignments: tuple[Assignment, ...]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "breakdown_id": self.breakdown_id,
            "department": self.department,
            "source_revision_id": self.source_revision_id,
            "elements": [item.to_dict() for item in self.elements],
            "decisions": [item.to_dict() for item in self.decisions],
            "notices": [item.to_dict() for item in self.notices],
            "assignments": [item.to_dict() for item in self.assignments],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DepartmentPacket:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            breakdown_id=str(data["breakdown_id"]),
            department=str(data["department"]),
            source_revision_id=str(data["source_revision_id"]),
            elements=tuple(
                BreakdownElement.from_dict(item) for item in data.get("elements", ())
            ),
            decisions=tuple(
                CraftDecision.from_dict(item) for item in data.get("decisions", ())
            ),
            notices=tuple(ChangeNotice.from_dict(item) for item in data.get("notices", ())),
            assignments=tuple(
                Assignment.from_dict(item) for item in data.get("assignments", ())
            ),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class OperationalEvent:
    event: ProjectEvent

    def to_dict(self) -> dict[str, Any]:
        return {"event": self.event.to_dict()}
