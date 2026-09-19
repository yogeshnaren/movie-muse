"""Storyboard frames, provenance, metrics, and role-distinct annotations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from movie_muse.director.api import AnnotationRole

DISCLAIMER = (
    "This storyboard is advisory visual development, not photographic coverage "
    "and not a live image-provider render."
)
IMAGE_PROVIDER_ENV = "MOVIE_MUSE_IMAGE_PROVIDER_BASE_URL"
TEMPLATE_ID = "tmpl_storyboard"
TEMPLATE_VERSION = "1.0"
RENDERER_VERSION = "deterministic-json/1"


@dataclass(frozen=True, slots=True)
class StoryboardAnnotation:
    id: str
    frame_id: str
    role: AnnotationRole
    body: str
    actor_id: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "frame_id": self.frame_id,
            "role": self.role.value,
            "body": self.body,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoryboardAnnotation:
        return cls(
            id=str(data["id"]),
            frame_id=str(data["frame_id"]),
            role=AnnotationRole(str(data["role"])),
            body=str(data["body"]),
            actor_id=str(data["actor_id"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class StoryboardMetrics:
    regeneration_count: int
    accept_count: int
    correction_count: int

    @property
    def regeneration_to_acceptance(self) -> float:
        if self.accept_count == 0:
            return float(self.regeneration_count)
        return self.regeneration_count / self.accept_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "regeneration_count": self.regeneration_count,
            "accept_count": self.accept_count,
            "correction_count": self.correction_count,
            "regeneration_to_acceptance": self.regeneration_to_acceptance,
        }


@dataclass(frozen=True, slots=True)
class StoryboardFrame:
    id: str
    project_id: str
    shot_id: str
    artifact_id: str
    artifact_version_id: str
    source_revision_id: str
    prompt: str
    input_fingerprint: str
    style_key: str
    character_key: str
    location_key: str
    provenance: dict[str, Any]
    accepted: bool = False
    labeled_stale: bool = False
    image_provider_used: bool = False
    reused_accepted_asset: bool = False
    regeneration_count: int = 0
    accept_count: int = 0
    correction_count: int = 0
    parent_id: str | None = None
    disclaimer: str = DISCLAIMER

    @property
    def metrics(self) -> StoryboardMetrics:
        return StoryboardMetrics(
            regeneration_count=self.regeneration_count,
            accept_count=self.accept_count,
            correction_count=self.correction_count,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "shot_id": self.shot_id,
            "artifact_id": self.artifact_id,
            "artifact_version_id": self.artifact_version_id,
            "source_revision_id": self.source_revision_id,
            "prompt": self.prompt,
            "input_fingerprint": self.input_fingerprint,
            "style_key": self.style_key,
            "character_key": self.character_key,
            "location_key": self.location_key,
            "provenance": dict(self.provenance),
            "accepted": self.accepted,
            "labeled_stale": self.labeled_stale,
            "image_provider_used": self.image_provider_used,
            "reused_accepted_asset": self.reused_accepted_asset,
            "regeneration_count": self.regeneration_count,
            "accept_count": self.accept_count,
            "correction_count": self.correction_count,
            "parent_id": self.parent_id,
            "disclaimer": self.disclaimer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoryboardFrame:
        provenance = data.get("provenance", {})
        if not isinstance(provenance, dict):
            raise ValueError("storyboard provenance is not an object")
        parent_id = data.get("parent_id")
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            shot_id=str(data["shot_id"]),
            artifact_id=str(data["artifact_id"]),
            artifact_version_id=str(data["artifact_version_id"]),
            source_revision_id=str(data["source_revision_id"]),
            prompt=str(data["prompt"]),
            input_fingerprint=str(data["input_fingerprint"]),
            style_key=str(data["style_key"]),
            character_key=str(data["character_key"]),
            location_key=str(data["location_key"]),
            provenance=dict(provenance),
            accepted=bool(data.get("accepted", False)),
            labeled_stale=bool(data.get("labeled_stale", False)),
            image_provider_used=bool(data.get("image_provider_used", False)),
            reused_accepted_asset=bool(data.get("reused_accepted_asset", False)),
            regeneration_count=int(data.get("regeneration_count", 0)),
            accept_count=int(data.get("accept_count", 0)),
            correction_count=int(data.get("correction_count", 0)),
            parent_id=str(parent_id) if parent_id else None,
            disclaimer=str(data.get("disclaimer", DISCLAIMER)),
        )
