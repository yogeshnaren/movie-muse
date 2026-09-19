"""Investor packs, cited claims, and delivery previews."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

DISCLAIMER = (
    "Investor materials cite current reviewed evidence. Commercial P10/P50/P90 "
    "ranges are not a guarantee. This pack does not fabricate credentials, "
    "attachments, or recipients."
)
FORBIDDEN_FABRICATION_PHRASES: tuple[str, ...] = (
    "fabricated credential",
    "fake accreditation",
    "invented attachment",
    "guaranteed investor",
    "sure-thing return",
)
TEMPLATE_ID = "tmpl_investor_artifacts"
TEMPLATE_VERSION = "1"
RENDERER_VERSION = "json/1"
TEMPLATE_BODY = (
    "{disclaimer}\nKIND {kind}\nPROJECT {project_id}\n"
    "BUDGET {budget_id}\nFORECAST {forecast_id}\nDATA_AS_OF {data_as_of}\n"
    "CLAIMS {claims}\nCITATIONS {citations}\nSOURCES {sources}\n"
)


class PackKind(str, Enum):
    DECK = "deck"
    ONE_PAGER = "one_pager"
    DATA_ROOM = "data_room"


@dataclass(frozen=True, slots=True)
class CitedClaim:
    id: str
    label: str
    value: str
    unit: str
    evidence_ref: str
    data_as_of: str
    method: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "evidence_ref": self.evidence_ref,
            "data_as_of": self.data_as_of,
            "method": self.method,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CitedClaim:
        return cls(
            id=str(data["id"]),
            label=str(data["label"]),
            value=str(data["value"]),
            unit=str(data["unit"]),
            evidence_ref=str(data["evidence_ref"]),
            data_as_of=str(data["data_as_of"]),
            method=str(data["method"]),
        )


@dataclass(frozen=True, slots=True)
class Citation:
    source_id: str
    rights_version_id: str
    use: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "rights_version_id": self.rights_version_id,
            "use": self.use,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Citation:
        return cls(
            source_id=str(data["source_id"]),
            rights_version_id=str(data["rights_version_id"]),
            use=str(data["use"]),
        )


@dataclass(frozen=True, slots=True)
class InvestorPack:
    id: str
    project_id: str
    kind: PackKind
    budget_id: str
    forecast_id: str
    source_version_ids: tuple[str, ...]
    claims: tuple[CitedClaim, ...]
    citations: tuple[Citation, ...]
    artifact_id: str
    artifact_version_id: str
    data_as_of: str
    locked_budget_total: str
    locked_p50: str
    disclaimer: str = DISCLAIMER
    previewed: bool = False
    approved: bool = False
    labeled_stale: bool = False
    rights_source_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "kind": self.kind.value,
            "budget_id": self.budget_id,
            "forecast_id": self.forecast_id,
            "source_version_ids": list(self.source_version_ids),
            "claims": [item.to_dict() for item in self.claims],
            "citations": [item.to_dict() for item in self.citations],
            "artifact_id": self.artifact_id,
            "artifact_version_id": self.artifact_version_id,
            "data_as_of": self.data_as_of,
            "locked_budget_total": self.locked_budget_total,
            "locked_p50": self.locked_p50,
            "disclaimer": self.disclaimer,
            "previewed": self.previewed,
            "approved": self.approved,
            "labeled_stale": self.labeled_stale,
            "rights_source_id": self.rights_source_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InvestorPack:
        source_version_ids = data.get("source_version_ids", ())
        claims = data.get("claims", ())
        citations = data.get("citations", ())
        if not isinstance(source_version_ids, list | tuple):
            raise ValueError("source_version_ids is not a list")
        if not isinstance(claims, list | tuple) or not isinstance(citations, list | tuple):
            raise ValueError("claims or citations is not a list")
        rights_source_id = data.get("rights_source_id")
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            kind=PackKind(str(data["kind"])),
            budget_id=str(data["budget_id"]),
            forecast_id=str(data["forecast_id"]),
            source_version_ids=tuple(str(item) for item in source_version_ids),
            claims=tuple(CitedClaim.from_dict(dict(item)) for item in claims),
            citations=tuple(Citation.from_dict(dict(item)) for item in citations),
            artifact_id=str(data["artifact_id"]),
            artifact_version_id=str(data["artifact_version_id"]),
            data_as_of=str(data["data_as_of"]),
            locked_budget_total=str(data["locked_budget_total"]),
            locked_p50=str(data["locked_p50"]),
            disclaimer=str(data.get("disclaimer", DISCLAIMER)),
            previewed=bool(data.get("previewed", False)),
            approved=bool(data.get("approved", False)),
            labeled_stale=bool(data.get("labeled_stale", False)),
            rights_source_id=str(rights_source_id) if rights_source_id else None,
        )


@dataclass(frozen=True, slots=True)
class PackPreview:
    pack_id: str
    recipient: str
    content: str
    render_id: str
    checksum: str
    channel: str = "investor_preview"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "recipient": self.recipient,
            "content": self.content,
            "render_id": self.render_id,
            "checksum": self.checksum,
            "channel": self.channel,
        }
