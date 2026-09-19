"""Reference Lens hits, rights context, and local index settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from movie_muse.retrieval.api import Citation
from movie_muse.rights.api import PermittedUse, SourceClassification, SourceValidationState


@dataclass(frozen=True, slots=True)
class RightsContext:
    classification: SourceClassification
    permitted_uses: tuple[PermittedUse, ...]
    validation_state: SourceValidationState
    license_summary: str | None
    rights_record_id: str | None
    why_permitted: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification.value,
            "permitted_uses": [item.value for item in self.permitted_uses],
            "validation_state": self.validation_state.value,
            "license_summary": self.license_summary,
            "rights_record_id": self.rights_record_id,
            "why_permitted": self.why_permitted,
        }


@dataclass(frozen=True, slots=True)
class CounterReference:
    source_id: str
    title: str
    contrast: str
    citation: Citation

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "contrast": self.contrast,
            "citation": self.citation.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class LensHit:
    id: str
    source_id: str
    title: str
    similarity: str
    relevant_passage: str
    structure_note: str
    difference: str
    why_surfaced: str
    rights: RightsContext
    citation: Citation
    redacted: bool
    score: float
    counter_reference: CounterReference | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "title": self.title,
            "similarity": self.similarity,
            "relevant_passage": self.relevant_passage,
            "structure_note": self.structure_note,
            "difference": self.difference,
            "why_surfaced": self.why_surfaced,
            "rights": self.rights.to_dict(),
            "citation": self.citation.to_dict(),
            "redacted": self.redacted,
            "score": self.score,
            "counter_reference": (
                self.counter_reference.to_dict() if self.counter_reference is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class LensSettings:
    project_id: str
    enabled: bool
    tombstoned_entry_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "enabled": self.enabled,
            "tombstoned_entry_ids": list(self.tombstoned_entry_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LensSettings:
        return cls(
            project_id=str(data["project_id"]),
            enabled=bool(data["enabled"]),
            tombstoned_entry_ids=tuple(str(item) for item in data.get("tombstoned_entry_ids", ())),
        )
