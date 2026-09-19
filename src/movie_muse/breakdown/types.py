"""Breakdown elements, evidence, and completeness reports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.schemas.api import ProductionProjection


class ElementKind(str, Enum):
    CAST = "cast"
    EXTRAS = "extras"
    LOCATION = "location"
    PROP = "prop"
    WARDROBE = "wardrobe"
    MAKEUP = "makeup"
    VEHICLE = "vehicle"
    ANIMAL = "animal"
    STUNT = "stunt"
    INTIMACY = "intimacy"
    MINOR = "minor"
    VFX = "vfx"
    SFX = "sfx"
    SOUND = "sound"
    EQUIPMENT = "equipment"
    PERMIT = "permit"
    SAFETY = "safety"
    TIMING = "timing"


class VerificationState(str, Enum):
    DERIVED = "derived"
    VERIFIED = "verified"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class ScreenplayEvidence:
    block_id: str
    scene_id: str | None
    excerpt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "scene_id": self.scene_id,
            "excerpt": self.excerpt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScreenplayEvidence:
        return cls(
            block_id=str(data["block_id"]),
            scene_id=str(data["scene_id"]) if data.get("scene_id") else None,
            excerpt=str(data["excerpt"]),
        )


@dataclass(frozen=True, slots=True)
class BreakdownElement:
    id: str
    kind: ElementKind
    name: str
    verification: VerificationState
    evidence: tuple[ScreenplayEvidence, ...]
    quantity: int = 1
    notes: str = ""
    verified_by_actor_id: str | None = None
    change_set_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": self.name,
            "verification": self.verification.value,
            "evidence": [item.to_dict() for item in self.evidence],
            "quantity": self.quantity,
            "notes": self.notes,
            "verified_by_actor_id": self.verified_by_actor_id,
            "change_set_id": self.change_set_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BreakdownElement:
        return cls(
            id=str(data["id"]),
            kind=ElementKind(str(data["kind"])),
            name=str(data["name"]),
            verification=VerificationState(str(data["verification"])),
            evidence=tuple(
                ScreenplayEvidence.from_dict(item) for item in data.get("evidence", ())
            ),
            quantity=int(data.get("quantity", 1)),
            notes=str(data.get("notes", "")),
            verified_by_actor_id=(
                str(data["verified_by_actor_id"]) if data.get("verified_by_actor_id") else None
            ),
            change_set_id=str(data["change_set_id"]) if data.get("change_set_id") else None,
        )


@dataclass(frozen=True, slots=True)
class CompletenessReport:
    completeness: float
    accuracy: float
    evidence_link_rate: float
    derived_count: int
    verified_count: int
    not_applicable_count: int
    meets_thresholds: bool
    current: bool
    labeled_stale: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "completeness": self.completeness,
            "accuracy": self.accuracy,
            "evidence_link_rate": self.evidence_link_rate,
            "derived_count": self.derived_count,
            "verified_count": self.verified_count,
            "not_applicable_count": self.not_applicable_count,
            "meets_thresholds": self.meets_thresholds,
            "current": self.current,
            "labeled_stale": self.labeled_stale,
        }


@dataclass(frozen=True, slots=True)
class PendingEdit:
    proposal_id: str
    breakdown_id: str
    element_id: str
    name: str | None
    quantity: int | None
    notes: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "breakdown_id": self.breakdown_id,
            "element_id": self.element_id,
            "name": self.name,
            "quantity": self.quantity,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PendingEdit:
        return cls(
            proposal_id=str(data["proposal_id"]),
            breakdown_id=str(data["breakdown_id"]),
            element_id=str(data["element_id"]),
            name=str(data["name"]) if data.get("name") is not None else None,
            quantity=int(data["quantity"]) if data.get("quantity") is not None else None,
            notes=str(data["notes"]) if data.get("notes") is not None else None,
        )


@dataclass(frozen=True, slots=True)
class StoredBreakdown:
    projection: ProductionProjection
    elements: tuple[BreakdownElement, ...]
    locked_revision_id: str
    config_node_id: str | None = None
    analysis_node_id: str | None = None
    labeled_stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection": self.projection.to_dict(),
            "elements": [item.to_dict() for item in self.elements],
            "locked_revision_id": self.locked_revision_id,
            "config_node_id": self.config_node_id,
            "analysis_node_id": self.analysis_node_id,
            "labeled_stale": self.labeled_stale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredBreakdown:
        raw = data["projection"]
        if not isinstance(raw, dict):
            raise ValueError("breakdown projection is not an object")
        return cls(
            projection=ProductionProjection.from_dict(raw),
            elements=tuple(
                BreakdownElement.from_dict(item) for item in data.get("elements", ())
            ),
            locked_revision_id=str(data["locked_revision_id"]),
            config_node_id=(
                str(data["config_node_id"]) if data.get("config_node_id") else None
            ),
            analysis_node_id=(
                str(data["analysis_node_id"]) if data.get("analysis_node_id") else None
            ),
            labeled_stale=bool(data.get("labeled_stale", False)),
        )
