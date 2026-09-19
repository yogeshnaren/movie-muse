"""Continuity findings, materiality, and reports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.authorization.api import Mode
from movie_muse.state_engine.api import StateDimension


class Materiality(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FindingCategory(str, Enum):
    CREATIVE = "creative"
    LOGISTICS = "logistics"


class FindingStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


LOGISTICS_DIMENSIONS = frozenset(
    {StateDimension.LOCATION, StateDimension.WORLD, StateDimension.WARDROBE}
)

PRODUCTION_MODES = frozenset({Mode.PRODUCER, Mode.AD, Mode.DEPARTMENT, Mode.FIELD})
AUTHOR_MODES = frozenset({Mode.WRITER, Mode.ROOM, Mode.DIRECTOR, Mode.INVESTOR})

BASE_MATERIALITY: dict[StateDimension, Materiality] = {
    StateDimension.KNOWLEDGE: Materiality.HIGH,
    StateDimension.POSSESSION: Materiality.HIGH,
    StateDimension.SECRET: Materiality.HIGH,
    StateDimension.ALLEGIANCE: Materiality.HIGH,
    StateDimension.RELATIONSHIP: Materiality.HIGH,
    StateDimension.OBJECTIVE: Materiality.HIGH,
    StateDimension.INJURY: Materiality.HIGH,
    StateDimension.BELIEF: Materiality.MEDIUM,
    StateDimension.CONFIRMATION: Materiality.MEDIUM,
    StateDimension.SUSPICION: Materiality.MEDIUM,
    StateDimension.SECOND_ORDER_BELIEF: Materiality.MEDIUM,
    StateDimension.MISUNDERSTANDING: Materiality.MEDIUM,
    StateDimension.LOCATION: Materiality.LOW,
    StateDimension.WORLD: Materiality.LOW,
    StateDimension.WARDROBE: Materiality.LOW,
}


def category_for(dimension: StateDimension) -> FindingCategory:
    if dimension in LOGISTICS_DIMENSIONS:
        return FindingCategory.LOGISTICS
    return FindingCategory.CREATIVE


def materiality_for(dimension: StateDimension, modes: tuple[Mode, ...]) -> Materiality:
    """Author mode compresses logistics; production mode may invert emphasis."""

    base = BASE_MATERIALITY.get(dimension, Materiality.MEDIUM)
    has_production = any(mode in PRODUCTION_MODES for mode in modes)
    has_author = any(mode in AUTHOR_MODES for mode in modes) or not modes
    if has_production and dimension in LOGISTICS_DIMENSIONS:
        return Materiality.HIGH
    if has_production and not has_author and base is Materiality.MEDIUM:
        return Materiality.LOW
    return base


@dataclass(frozen=True, slots=True)
class FindingDisposition:
    status: FindingStatus
    actor_id: str
    created_at: str
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FindingDisposition:
        return cls(
            status=FindingStatus(str(data["status"])),
            actor_id=str(data["actor_id"]),
            created_at=str(data["created_at"]),
            note=str(data.get("note", "")),
        )


@dataclass(frozen=True, slots=True)
class ContinuityFinding:
    id: str
    source_id: str
    scene_id: str
    subject_id: str
    dimension: StateDimension
    attribute: str
    materiality: Materiality
    category: FindingCategory
    status: FindingStatus
    evidence_ids: tuple[str, ...]
    reason: str
    revision_id: str
    project_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "scene_id": self.scene_id,
            "subject_id": self.subject_id,
            "dimension": self.dimension.value,
            "attribute": self.attribute,
            "materiality": self.materiality.value,
            "category": self.category.value,
            "status": self.status.value,
            "evidence_ids": list(self.evidence_ids),
            "reason": self.reason,
            "revision_id": self.revision_id,
            "project_id": self.project_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContinuityFinding:
        return cls(
            id=str(data["id"]),
            source_id=str(data["source_id"]),
            scene_id=str(data["scene_id"]),
            subject_id=str(data["subject_id"]),
            dimension=StateDimension(str(data["dimension"])),
            attribute=str(data["attribute"]),
            materiality=Materiality(str(data["materiality"])),
            category=FindingCategory(str(data["category"])),
            status=FindingStatus(str(data["status"])),
            evidence_ids=tuple(str(item) for item in data.get("evidence_ids", ())),
            reason=str(data["reason"]),
            revision_id=str(data["revision_id"]),
            project_id=str(data["project_id"]),
        )


@dataclass(frozen=True, slots=True)
class ContinuityReport:
    revision_id: str
    project_id: str
    mode: tuple[Mode, ...]
    findings: tuple[ContinuityFinding, ...]
    hidden_finding_ids: tuple[str, ...]
    projection_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "project_id": self.project_id,
            "mode": [item.value for item in self.mode],
            "findings": [item.to_dict() for item in self.findings],
            "hidden_finding_ids": list(self.hidden_finding_ids),
            "projection_id": self.projection_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContinuityReport:
        return cls(
            revision_id=str(data["revision_id"]),
            project_id=str(data["project_id"]),
            mode=tuple(Mode(str(item)) for item in data.get("mode", ())),
            findings=tuple(ContinuityFinding.from_dict(item) for item in data.get("findings", ())),
            hidden_finding_ids=tuple(str(item) for item in data.get("hidden_finding_ids", ())),
            projection_id=str(data["projection_id"]),
        )
