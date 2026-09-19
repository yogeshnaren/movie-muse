"""Video previs clips, cost ranges, timelines, and intended-effect reviews."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

DISCLAIMER = (
    "This output is labeled previs, not the finished film, and is not a live "
    "video-provider render."
)
CONTINUITY_LIMITATIONS = (
    "Generated previs cannot guarantee continuity with live-action coverage, "
    "locked ShotIR attributes, or storyboard frames."
)
VIDEO_PROVIDER_ENV = "MOVIE_MUSE_VIDEO_PROVIDER_BASE_URL"
TEMPLATE_ID = "tmpl_video_previs"
TEMPLATE_VERSION = "1.0"
RENDERER_VERSION = "deterministic-json/1"
WORKER_ID = "video-previs-local"
JOB_TYPE = "video_previs.render"


class ConsentState(str, Enum):
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"


class TimelineKind(str, Enum):
    TIMELINE = "timeline"
    ANIMATIC = "animatic"


@dataclass(frozen=True, slots=True)
class CostRange:
    estimated_cost: float
    low: float
    high: float
    currency: str
    quote_id: str
    paid: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimated_cost": self.estimated_cost,
            "low": self.low,
            "high": self.high,
            "currency": self.currency,
            "quote_id": self.quote_id,
            "paid": self.paid,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CostRange:
        return cls(
            estimated_cost=float(data["estimated_cost"]),
            low=float(data["low"]),
            high=float(data["high"]),
            currency=str(data["currency"]),
            quote_id=str(data["quote_id"]),
            paid=bool(data.get("paid", False)),
        )


@dataclass(frozen=True, slots=True)
class ConsentRecord:
    project_id: str
    state: ConsentState
    actor_id: str | None = None
    decided_at: str | None = None

    @property
    def granted(self) -> bool:
        return self.state is ConsentState.GRANTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "state": self.state.value,
            "actor_id": self.actor_id,
            "decided_at": self.decided_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConsentRecord:
        actor_id = data.get("actor_id")
        decided_at = data.get("decided_at")
        return cls(
            project_id=str(data["project_id"]),
            state=ConsentState(str(data.get("state", ConsentState.PENDING.value))),
            actor_id=str(actor_id) if actor_id else None,
            decided_at=str(decided_at) if decided_at else None,
        )


@dataclass(frozen=True, slots=True)
class IntendedEffectReview:
    id: str
    project_id: str
    subject_id: str
    notes: str
    actor_id: str
    created_at: str
    promotes_to_canon: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "subject_id": self.subject_id,
            "notes": self.notes,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
            "promotes_to_canon": self.promotes_to_canon,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntendedEffectReview:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            subject_id=str(data["subject_id"]),
            notes=str(data["notes"]),
            actor_id=str(data["actor_id"]),
            created_at=str(data["created_at"]),
            promotes_to_canon=bool(data.get("promotes_to_canon", False)),
        )


@dataclass(frozen=True, slots=True)
class VideoClip:
    id: str
    project_id: str
    shot_id: str
    job_id: str
    source_revision_id: str
    prompt: str
    input_fingerprint: str
    estimated_cost_low: float
    estimated_cost_high: float
    storyboard_frame_id: str | None = None
    artifact_id: str = ""
    artifact_version_id: str = ""
    provenance: dict[str, Any] | None = None
    actual_cost: float = 0.0
    accepted: bool = False
    labeled_stale: bool = False
    video_provider_used: bool = False
    reused_accepted_asset: bool = False
    labeled_previs: bool = True
    canon: bool = False
    regeneration_count: int = 0
    parent_id: str | None = None
    disclaimer: str = DISCLAIMER
    continuity_limitations: str = CONTINUITY_LIMITATIONS

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "shot_id": self.shot_id,
            "job_id": self.job_id,
            "source_revision_id": self.source_revision_id,
            "prompt": self.prompt,
            "input_fingerprint": self.input_fingerprint,
            "estimated_cost_low": self.estimated_cost_low,
            "estimated_cost_high": self.estimated_cost_high,
            "storyboard_frame_id": self.storyboard_frame_id,
            "artifact_id": self.artifact_id,
            "artifact_version_id": self.artifact_version_id,
            "provenance": dict(self.provenance or {}),
            "actual_cost": self.actual_cost,
            "accepted": self.accepted,
            "labeled_stale": self.labeled_stale,
            "video_provider_used": self.video_provider_used,
            "reused_accepted_asset": self.reused_accepted_asset,
            "labeled_previs": self.labeled_previs,
            "canon": self.canon,
            "regeneration_count": self.regeneration_count,
            "parent_id": self.parent_id,
            "disclaimer": self.disclaimer,
            "continuity_limitations": self.continuity_limitations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VideoClip:
        provenance = data.get("provenance") or {}
        if not isinstance(provenance, dict):
            raise ValueError("video previs provenance is not an object")
        frame_id = data.get("storyboard_frame_id")
        parent_id = data.get("parent_id")
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            shot_id=str(data["shot_id"]),
            job_id=str(data["job_id"]),
            source_revision_id=str(data["source_revision_id"]),
            prompt=str(data["prompt"]),
            input_fingerprint=str(data["input_fingerprint"]),
            estimated_cost_low=float(data["estimated_cost_low"]),
            estimated_cost_high=float(data["estimated_cost_high"]),
            storyboard_frame_id=str(frame_id) if frame_id else None,
            artifact_id=str(data.get("artifact_id", "")),
            artifact_version_id=str(data.get("artifact_version_id", "")),
            provenance=dict(provenance),
            actual_cost=float(data.get("actual_cost", 0.0)),
            accepted=bool(data.get("accepted", False)),
            labeled_stale=bool(data.get("labeled_stale", False)),
            video_provider_used=bool(data.get("video_provider_used", False)),
            reused_accepted_asset=bool(data.get("reused_accepted_asset", False)),
            labeled_previs=bool(data.get("labeled_previs", True)),
            canon=bool(data.get("canon", False)),
            regeneration_count=int(data.get("regeneration_count", 0)),
            parent_id=str(parent_id) if parent_id else None,
            disclaimer=str(data.get("disclaimer", DISCLAIMER)),
            continuity_limitations=str(
                data.get("continuity_limitations", CONTINUITY_LIMITATIONS)
            ),
        )


@dataclass(frozen=True, slots=True)
class PrevisTimeline:
    id: str
    project_id: str
    clip_ids: tuple[str, ...]
    artifact_id: str
    artifact_version_id: str
    kind: TimelineKind = TimelineKind.TIMELINE
    labeled_previs: bool = True
    canon: bool = False
    disclaimer: str = DISCLAIMER
    continuity_limitations: str = CONTINUITY_LIMITATIONS

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "clip_ids": list(self.clip_ids),
            "artifact_id": self.artifact_id,
            "artifact_version_id": self.artifact_version_id,
            "kind": self.kind.value,
            "labeled_previs": self.labeled_previs,
            "canon": self.canon,
            "disclaimer": self.disclaimer,
            "continuity_limitations": self.continuity_limitations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PrevisTimeline:
        raw_ids = data.get("clip_ids", ())
        if not isinstance(raw_ids, list | tuple):
            raise ValueError("timeline clip_ids is not a list")
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            clip_ids=tuple(str(item) for item in raw_ids),
            artifact_id=str(data["artifact_id"]),
            artifact_version_id=str(data["artifact_version_id"]),
            kind=TimelineKind(str(data.get("kind", TimelineKind.TIMELINE.value))),
            labeled_previs=bool(data.get("labeled_previs", True)),
            canon=bool(data.get("canon", False)),
            disclaimer=str(data.get("disclaimer", DISCLAIMER)),
            continuity_limitations=str(
                data.get("continuity_limitations", CONTINUITY_LIMITATIONS)
            ),
        )
