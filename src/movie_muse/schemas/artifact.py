"""Artifact / ArtifactVersion — the generic artifact subsystem's schema shape.

Architecture §9: implement Artifact, ArtifactVersion, ArtifactTemplate,
ArtifactRender, ArtifactLink, and DeliveryRecord before any specialized
decks/emails/reports/schedules/budgets/storyboards/insurance packets.
MM-002 defines the versioned Artifact/ArtifactVersion shape; MM-007 builds
the full subsystem (templates, rendering, delivery, review workflow) on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from movie_muse.schemas.serialization import dataclass_from_dict, dataclass_to_dict, sealed


class ArtifactStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    ARCHIVED = "archived"


@sealed
@dataclass(frozen=True, slots=True)
class Artifact:
    SCHEMA_NAME: ClassVar[str] = "artifact"

    id: str
    project_id: str
    artifact_type: str
    title: str
    created_at: str
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Artifact:
        return dataclass_from_dict(cls, data)


@sealed
@dataclass(frozen=True, slots=True)
class ArtifactVersion:
    SCHEMA_NAME: ClassVar[str] = "artifact_version"

    id: str
    artifact_id: str
    source_revision_id: str
    template_id: str
    template_version: str
    renderer_version: str
    checksum: str
    created_at: str
    creator_actor_id: str
    status: ArtifactStatus = ArtifactStatus.DRAFT
    evidence_bundle_ids: tuple[str, ...] = ()
    rights_record_ids: tuple[str, ...] = ()
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactVersion:
        return dataclass_from_dict(
            cls,
            data,
            converters={
                "status": ArtifactStatus,
                "evidence_bundle_ids": tuple,
                "rights_record_ids": tuple,
            },
        )
