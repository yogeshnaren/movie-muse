"""DirectorVisionGraph, SceneSpace records, annotations, coverage, constraints."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.schemas.api import SceneSpace, SubjectPosition


class AnnotationRole(str, Enum):
    WRITER = "writer"
    DIRECTOR = "director"
    PRODUCER = "producer"


class CoveragePurpose(str, Enum):
    MASTER = "master"
    COVERAGE = "coverage"
    INSERT = "insert"
    REVERSE = "reverse"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class SemanticAnchor:
    id: str
    token: str
    kind: str
    page_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "token": self.token,
            "kind": self.kind,
            "page_id": self.page_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticAnchor:
        return cls(
            id=str(data["id"]),
            token=str(data["token"]),
            kind=str(data["kind"]),
            page_id=str(data.get("page_id", "")),
        )


@dataclass(frozen=True, slots=True)
class RoleAnnotation:
    id: str
    project_id: str
    role: AnnotationRole
    target_kind: str
    target_id: str
    body: str
    actor_id: str
    created_at: str
    anchor: SemanticAnchor

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "role": self.role.value,
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "body": self.body,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
            "anchor": self.anchor.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoleAnnotation:
        raw_anchor = data["anchor"]
        if not isinstance(raw_anchor, dict):
            raise ValueError("annotation anchor is not an object")
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            role=AnnotationRole(str(data["role"])),
            target_kind=str(data["target_kind"]),
            target_id=str(data["target_id"]),
            body=str(data["body"]),
            actor_id=str(data["actor_id"]),
            created_at=str(data["created_at"]),
            anchor=SemanticAnchor.from_dict(raw_anchor),
        )


@dataclass(frozen=True, slots=True)
class CoverageBeat:
    id: str
    project_id: str
    scene_space_id: str
    purpose: CoveragePurpose
    shot_ids: tuple[str, ...]
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "scene_space_id": self.scene_space_id,
            "purpose": self.purpose.value,
            "shot_ids": list(self.shot_ids),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoverageBeat:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            scene_space_id=str(data["scene_space_id"]),
            purpose=CoveragePurpose(str(data["purpose"])),
            shot_ids=tuple(str(item) for item in data.get("shot_ids", ())),
            notes=str(data.get("notes", "")),
        )


@dataclass(frozen=True, slots=True)
class ProducerConstraint:
    id: str
    project_id: str
    target_kind: str
    target_id: str
    statement: str
    actor_id: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "statement": self.statement,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProducerConstraint:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            target_kind=str(data["target_kind"]),
            target_id=str(data["target_id"]),
            statement=str(data["statement"]),
            actor_id=str(data["actor_id"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class SceneSpaceRecord:
    space: SceneSpace
    project_id: str
    created_by_actor_id: str
    created_at: str
    config_node_id: str | None = None
    continuity_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "space": self.space.to_dict(),
            "project_id": self.project_id,
            "created_by_actor_id": self.created_by_actor_id,
            "created_at": self.created_at,
            "config_node_id": self.config_node_id,
            "continuity_notes": self.continuity_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SceneSpaceRecord:
        raw_space = data["space"]
        if not isinstance(raw_space, dict):
            raise ValueError("scene space payload is not an object")
        return cls(
            space=SceneSpace.from_dict(raw_space),
            project_id=str(data["project_id"]),
            created_by_actor_id=str(data["created_by_actor_id"]),
            created_at=str(data["created_at"]),
            config_node_id=(
                str(data["config_node_id"]) if data.get("config_node_id") else None
            ),
            continuity_notes=str(data.get("continuity_notes", "")),
        )


@dataclass(frozen=True, slots=True)
class DirectorVisionGraph:
    project_id: str
    generation_enabled: bool
    scene_space_ids: tuple[str, ...]
    shot_ids: tuple[str, ...]
    coverage_ids: tuple[str, ...]
    constraint_ids: tuple[str, ...]
    annotation_ids: tuple[str, ...]
    provider_independent: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "generation_enabled": self.generation_enabled,
            "scene_space_ids": list(self.scene_space_ids),
            "shot_ids": list(self.shot_ids),
            "coverage_ids": list(self.coverage_ids),
            "constraint_ids": list(self.constraint_ids),
            "annotation_ids": list(self.annotation_ids),
            "provider_independent": self.provider_independent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DirectorVisionGraph:
        return cls(
            project_id=str(data["project_id"]),
            generation_enabled=bool(data.get("generation_enabled", False)),
            scene_space_ids=tuple(str(item) for item in data.get("scene_space_ids", ())),
            shot_ids=tuple(str(item) for item in data.get("shot_ids", ())),
            coverage_ids=tuple(str(item) for item in data.get("coverage_ids", ())),
            constraint_ids=tuple(str(item) for item in data.get("constraint_ids", ())),
            annotation_ids=tuple(str(item) for item in data.get("annotation_ids", ())),
            provider_independent=bool(data.get("provider_independent", True)),
        )


__all__ = [
    "AnnotationRole",
    "CoverageBeat",
    "CoveragePurpose",
    "DirectorVisionGraph",
    "ProducerConstraint",
    "RoleAnnotation",
    "SceneSpaceRecord",
    "SemanticAnchor",
    "SubjectPosition",
]
