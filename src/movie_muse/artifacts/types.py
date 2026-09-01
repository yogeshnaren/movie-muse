"""Immutable module-owned types for templates, renders, links, and delivery."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from movie_muse.schemas.api import ArtifactVersion, ArtifactStatus


class ArtifactType(str, Enum):
    DOCUMENT = "document"
    TABLE = "table"
    MEDIA = "media"
    PACKAGE = "package"


class ArtifactClassification(str, Enum):
    INTERNAL = "internal"
    RESTRICTED = "restricted"


class RenderPurpose(str, Enum):
    GENERATION = "generation"
    REGENERATION = "regeneration"
    PREVIEW = "preview"
    EXPORT = "export"


@dataclass(frozen=True, slots=True)
class ArtifactTemplate:
    id: str
    project_id: str
    version: str
    renderer_version: str
    body: str
    creator_actor_id: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "version": self.version,
            "renderer_version": self.renderer_version,
            "body": self.body,
            "creator_actor_id": self.creator_actor_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactTemplate:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            version=str(data["version"]),
            renderer_version=str(data["renderer_version"]),
            body=str(data["body"]),
            creator_actor_id=str(data["creator_actor_id"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class StoredArtifactVersion:
    """Immutable generated version plus module metadata omitted from MM-002."""

    version: ArtifactVersion
    inputs_json: str
    classification: ArtifactClassification
    editor_actor_id: str
    render_id: str

    @property
    def inputs(self) -> Mapping[str, Any]:
        decoded = json.loads(self.inputs_json)
        if not isinstance(decoded, dict):
            raise ValueError("artifact inputs are not an object")
        return _freeze_mapping(decoded)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version.to_dict(),
            "inputs_json": self.inputs_json,
            "classification": self.classification.value,
            "editor_actor_id": self.editor_actor_id,
            "render_id": self.render_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredArtifactVersion:
        return cls(
            version=ArtifactVersion.from_dict(_dict(data["version"])),
            inputs_json=str(data["inputs_json"]),
            classification=ArtifactClassification(str(data["classification"])),
            editor_actor_id=str(data["editor_actor_id"]),
            render_id=str(data["render_id"]),
        )


@dataclass(frozen=True, slots=True)
class ReviewRecord:
    id: str
    artifact_version_id: str
    from_status: ArtifactStatus
    to_status: ArtifactStatus
    actor_id: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "artifact_version_id": self.artifact_version_id,
            "from_status": self.from_status.value,
            "to_status": self.to_status.value,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewRecord:
        return cls(
            id=str(data["id"]),
            artifact_version_id=str(data["artifact_version_id"]),
            from_status=ArtifactStatus(str(data["from_status"])),
            to_status=ArtifactStatus(str(data["to_status"])),
            actor_id=str(data["actor_id"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class ArtifactVersionView:
    record: StoredArtifactVersion
    status: ArtifactStatus
    latest_review: ReviewRecord | None = None

    @property
    def version(self) -> ArtifactVersion:
        return self.record.version


@dataclass(frozen=True, slots=True)
class ArtifactRender:
    id: str
    artifact_version_id: str
    source_revision_id: str
    template_id: str
    template_version: str
    renderer_version: str
    checksum: str
    blob_digest: str
    purpose: RenderPurpose
    actor_id: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "artifact_version_id": self.artifact_version_id,
            "source_revision_id": self.source_revision_id,
            "template_id": self.template_id,
            "template_version": self.template_version,
            "renderer_version": self.renderer_version,
            "checksum": self.checksum,
            "blob_digest": self.blob_digest,
            "purpose": self.purpose.value,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactRender:
        return cls(
            id=str(data["id"]),
            artifact_version_id=str(data["artifact_version_id"]),
            source_revision_id=str(data["source_revision_id"]),
            template_id=str(data["template_id"]),
            template_version=str(data["template_version"]),
            renderer_version=str(data["renderer_version"]),
            checksum=str(data["checksum"]),
            blob_digest=str(data["blob_digest"]),
            purpose=RenderPurpose(str(data["purpose"])),
            actor_id=str(data["actor_id"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class RenderResult:
    render: ArtifactRender
    content: bytes


@dataclass(frozen=True, slots=True)
class ArtifactLink:
    id: str
    artifact_id: str
    artifact_version_id: str
    source_revision_id: str
    relation: str
    actor_id: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "artifact_id": self.artifact_id,
            "artifact_version_id": self.artifact_version_id,
            "source_revision_id": self.source_revision_id,
            "relation": self.relation,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactLink:
        return cls(
            id=str(data["id"]),
            artifact_id=str(data["artifact_id"]),
            artifact_version_id=str(data["artifact_version_id"]),
            source_revision_id=str(data["source_revision_id"]),
            relation=str(data["relation"]),
            actor_id=str(data["actor_id"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class DeliveryRecord:
    id: str
    artifact_version_id: str
    preview_render_id: str
    preview_checksum: str
    channel: str
    recipient: str
    actor_id: str
    created_at: str
    network_sent: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "artifact_version_id": self.artifact_version_id,
            "preview_render_id": self.preview_render_id,
            "preview_checksum": self.preview_checksum,
            "channel": self.channel,
            "recipient": self.recipient,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
            "network_sent": self.network_sent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeliveryRecord:
        return cls(
            id=str(data["id"]),
            artifact_version_id=str(data["artifact_version_id"]),
            preview_render_id=str(data["preview_render_id"]),
            preview_checksum=str(data["preview_checksum"]),
            channel=str(data["channel"]),
            recipient=str(data["recipient"]),
            actor_id=str(data["actor_id"]),
            created_at=str(data["created_at"]),
            network_sent=bool(data.get("network_sent", False)),
        )


@dataclass(frozen=True, slots=True)
class ArtifactComparison:
    left_version_id: str
    right_version_id: str
    checksum_changed: bool
    status_changed: bool
    source_revision_changed: bool
    inputs_changed: bool
    changed_input_keys: tuple[str, ...]


def _dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("expected object")
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _freeze_mapping(value: dict[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
