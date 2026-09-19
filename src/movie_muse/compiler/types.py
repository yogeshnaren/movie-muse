"""Deterministic compile artifacts. These are structural, not inferred."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMPILER_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class CompiledScene:
    scene_id: str
    heading: str
    int_ext: str | None
    location: str | None
    time_of_day: str | None
    scene_number: str | None
    heading_block_id: str
    character_names: tuple[str, ...]
    block_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "heading": self.heading,
            "int_ext": self.int_ext,
            "location": self.location,
            "time_of_day": self.time_of_day,
            "scene_number": self.scene_number,
            "heading_block_id": self.heading_block_id,
            "character_names": list(self.character_names),
            "block_ids": list(self.block_ids),
        }


@dataclass(frozen=True, slots=True)
class CompiledEntity:
    kind: str
    canonical_name: str
    scene_ids: tuple[str, ...]
    mention_block_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "canonical_name": self.canonical_name,
            "scene_ids": list(self.scene_ids),
            "mention_block_ids": list(self.mention_block_ids),
        }


@dataclass(frozen=True, slots=True)
class CompiledScreenplay:
    project_id: str
    document_id: str
    source_revision_id: str
    compiler_version: str
    scenes: tuple[CompiledScene, ...]
    entities: tuple[CompiledEntity, ...]
    scene_order: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "document_id": self.document_id,
            "source_revision_id": self.source_revision_id,
            "compiler_version": self.compiler_version,
            "scenes": [scene.to_dict() for scene in self.scenes],
            "entities": [entity.to_dict() for entity in self.entities],
            "scene_order": list(self.scene_order),
        }
