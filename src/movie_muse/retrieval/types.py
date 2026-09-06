"""Immutable retrieval records and citations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from movie_muse.rights.api import PermittedUse, SourceClassification, SourceValidationState


@dataclass(frozen=True, slots=True)
class Citation:
    source_id: str
    source_version_id: str
    title: str
    rights_record_id: str | None
    license_summary: str | None
    classification: SourceClassification
    permitted_uses: tuple[PermittedUse, ...]
    validation_state: SourceValidationState

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_version_id": self.source_version_id,
            "title": self.title,
            "rights_record_id": self.rights_record_id,
            "license_summary": self.license_summary,
            "classification": self.classification.value,
            "permitted_uses": [item.value for item in self.permitted_uses],
            "validation_state": self.validation_state.value,
        }


@dataclass(frozen=True, slots=True)
class IndexedReference:
    id: str
    source_id: str
    project_id: str
    title: str
    text: str
    indexed_at: str
    indexed_by: str
    classification: SourceClassification
    permitted_uses: tuple[PermittedUse, ...]
    validation_state: SourceValidationState
    rights_record_id: str | None
    source_version_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "project_id": self.project_id,
            "title": self.title,
            "text": self.text,
            "indexed_at": self.indexed_at,
            "indexed_by": self.indexed_by,
            "classification": self.classification.value,
            "permitted_uses": [item.value for item in self.permitted_uses],
            "validation_state": self.validation_state.value,
            "rights_record_id": self.rights_record_id,
            "source_version_id": self.source_version_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IndexedReference:
        return cls(
            id=str(data["id"]),
            source_id=str(data["source_id"]),
            project_id=str(data["project_id"]),
            title=str(data["title"]),
            text=str(data["text"]),
            indexed_at=str(data["indexed_at"]),
            indexed_by=str(data["indexed_by"]),
            classification=SourceClassification(str(data["classification"])),
            permitted_uses=tuple(
                PermittedUse(str(item)) for item in data.get("permitted_uses", ())
            ),
            validation_state=SourceValidationState(str(data["validation_state"])),
            rights_record_id=(
                str(data["rights_record_id"])
                if data.get("rights_record_id") is not None
                else None
            ),
            source_version_id=str(data["source_version_id"]),
        )


@dataclass(frozen=True, slots=True)
class RetrievedSegment:
    id: str
    project_id: str
    source_id: str
    text: str
    score: float
    citation: Citation
    redacted: bool
    untrusted: bool = True

    @property
    def source_ids(self) -> tuple[str, ...]:
        extras = (self.citation.rights_record_id,) if self.citation.rights_record_id else ()
        return (self.source_id, self.citation.source_version_id, *extras)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "source_id": self.source_id,
            "text": self.text,
            "score": self.score,
            "citation": self.citation.to_dict(),
            "redacted": self.redacted,
            "untrusted": self.untrusted,
            "source_ids": list(self.source_ids),
        }
