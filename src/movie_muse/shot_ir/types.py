"""Stored ShotIR envelopes, shot cards, and continuity overlays."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from movie_muse.schemas.api import CameraSpec, ShotIR


@dataclass(frozen=True, slots=True)
class StoredShot:
    record: ShotIR
    project_id: str
    created_by_actor_id: str
    color_intent: str = ""
    continuity_notes: str = ""
    coverage_purpose: str = ""
    analysis_node_id: str | None = None
    labeled_stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "record": self.record.to_dict(),
            "project_id": self.project_id,
            "created_by_actor_id": self.created_by_actor_id,
            "color_intent": self.color_intent,
            "continuity_notes": self.continuity_notes,
            "coverage_purpose": self.coverage_purpose,
            "analysis_node_id": self.analysis_node_id,
            "labeled_stale": self.labeled_stale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredShot:
        raw = data["record"]
        if not isinstance(raw, dict):
            raise ValueError("shot record is not an object")
        return cls(
            record=ShotIR.from_dict(raw),
            project_id=str(data["project_id"]),
            created_by_actor_id=str(data["created_by_actor_id"]),
            color_intent=str(data.get("color_intent", "")),
            continuity_notes=str(data.get("continuity_notes", "")),
            coverage_purpose=str(data.get("coverage_purpose", "")),
            analysis_node_id=(
                str(data["analysis_node_id"]) if data.get("analysis_node_id") else None
            ),
            labeled_stale=bool(data.get("labeled_stale", False)),
        )


@dataclass(frozen=True, slots=True)
class ShotCard:
    shot_id: str
    scene_space_id: str
    diagram: str
    camera_summary: str
    blocking_summary: str
    generation_used: bool
    mode: str
    generation_enabled: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "scene_space_id": self.scene_space_id,
            "diagram": self.diagram,
            "camera_summary": self.camera_summary,
            "blocking_summary": self.blocking_summary,
            "generation_used": self.generation_used,
            "mode": self.mode,
            "generation_enabled": self.generation_enabled,
        }


__all__ = ["CameraSpec", "ShotCard", "ShotIR", "StoredShot"]
