"""Risk inventory, missing-information checklist, and readiness packets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from movie_muse.schemas.api import ProductionProjection

DISCLAIMER = (
    "READINESS SUPPORT ONLY. This package is not underwriting, not binding, "
    "and not coverage. It does not issue insurance or replace a broker or underwriter."
)

FORBIDDEN_COVERAGE_PHRASES = (
    "policy is bound",
    "coverage issued",
    "underwritten as bound",
    "this is insurance",
)


@dataclass(frozen=True, slots=True)
class RiskItem:
    id: str
    kind: str
    name: str
    scene_ids: tuple[str, ...]
    evidence_excerpt: str
    verified: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "scene_ids": list(self.scene_ids),
            "evidence_excerpt": self.evidence_excerpt,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RiskItem:
        return cls(
            id=str(data["id"]),
            kind=str(data["kind"]),
            name=str(data["name"]),
            scene_ids=tuple(str(item) for item in data.get("scene_ids", ())),
            evidence_excerpt=str(data.get("evidence_excerpt", "")),
            verified=bool(data.get("verified", False)),
        )


@dataclass(frozen=True, slots=True)
class MissingItem:
    code: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MissingItem:
        return cls(code=str(data["code"]), detail=str(data["detail"]))


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    kind: str
    name: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "name": self.name, "detail": self.detail}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceItem:
        return cls(kind=str(data["kind"]), name=str(data["name"]), detail=str(data["detail"]))


@dataclass(frozen=True, slots=True)
class HandoffPreview:
    packet_id: str
    recipient: str
    content: str
    render_id: str
    checksum: str
    channel: str


@dataclass(frozen=True, slots=True)
class StoredPacket:
    projection: ProductionProjection
    budget_id: str
    schedule_id: str
    breakdown_id: str
    disclaimer: str
    risks: tuple[RiskItem, ...]
    missing: tuple[MissingItem, ...]
    evidence: tuple[EvidenceItem, ...]
    disclosures: tuple[str, ...]
    artifact_id: str
    artifact_version_id: str
    previewed: bool = False
    approved: bool = False
    labeled_stale: bool = False
    config_node_id: str | None = None
    analysis_node_id: str | None = None

    @property
    def id(self) -> str:
        return self.projection.id

    @property
    def project_id(self) -> str:
        return self.projection.project_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection": self.projection.to_dict(),
            "budget_id": self.budget_id,
            "schedule_id": self.schedule_id,
            "breakdown_id": self.breakdown_id,
            "disclaimer": self.disclaimer,
            "risks": [item.to_dict() for item in self.risks],
            "missing": [item.to_dict() for item in self.missing],
            "evidence": [item.to_dict() for item in self.evidence],
            "disclosures": list(self.disclosures),
            "artifact_id": self.artifact_id,
            "artifact_version_id": self.artifact_version_id,
            "previewed": self.previewed,
            "approved": self.approved,
            "labeled_stale": self.labeled_stale,
            "config_node_id": self.config_node_id,
            "analysis_node_id": self.analysis_node_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredPacket:
        return cls(
            projection=ProductionProjection.from_dict(data["projection"]),
            budget_id=str(data["budget_id"]),
            schedule_id=str(data["schedule_id"]),
            breakdown_id=str(data["breakdown_id"]),
            disclaimer=str(data["disclaimer"]),
            risks=tuple(RiskItem.from_dict(item) for item in data.get("risks", ())),
            missing=tuple(MissingItem.from_dict(item) for item in data.get("missing", ())),
            evidence=tuple(EvidenceItem.from_dict(item) for item in data.get("evidence", ())),
            disclosures=tuple(str(item) for item in data.get("disclosures", ())),
            artifact_id=str(data["artifact_id"]),
            artifact_version_id=str(data["artifact_version_id"]),
            previewed=bool(data.get("previewed", False)),
            approved=bool(data.get("approved", False)),
            labeled_stale=bool(data.get("labeled_stale", False)),
            config_node_id=str(data["config_node_id"]) if data.get("config_node_id") else None,
            analysis_node_id=(
                str(data["analysis_node_id"]) if data.get("analysis_node_id") else None
            ),
        )
