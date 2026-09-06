"""Evidence Bundle, method provenance, lineage, and export-disclosure types.

MethodProvenance is compatible with MM-009 ModelProvenance field names but does
not import ``movie_muse.model_router`` internals. Callers may pass a mapping
produced by ``ModelProvenance.to_dict()``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.provenance.errors import ChainOfThoughtRejectedError
from movie_muse.schemas.api import CitedSource, EvidenceBundle, HumanValidationState

CHAIN_OF_THOUGHT_MARKERS = ("chain_of_thought", "chain-of-thought", "<thinking>")

FORECAST_DISCLAIMER = "Forecasts are scenarios, not guarantees."
SYNTHETIC_AUDIENCE_DISCLAIMER = "Synthetic audiences are hypotheses, not human samples."


class ClaimKind(str, Enum):
    CLAIM = "claim"
    RECOMMENDATION = "recommendation"
    FORECAST_SCENARIO = "forecast_scenario"
    SYNTHETIC_AUDIENCE_HYPOTHESIS = "synthetic_audience_hypothesis"


def contains_chain_of_thought(value: object) -> bool:
    """Return True when a payload includes private chain-of-thought material."""

    if isinstance(value, Mapping):
        for key, inner in value.items():
            lowered = str(key).lower().replace("-", "_")
            if "chain_of_thought" in lowered:
                return True
            if contains_chain_of_thought(inner):
                return True
        return False
    if isinstance(value, list | tuple):
        return any(contains_chain_of_thought(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(marker in lowered for marker in CHAIN_OF_THOUGHT_MARKERS)
    return False


def reject_chain_of_thought(payload: object, *, field: str = "payload") -> None:
    if contains_chain_of_thought(payload):
        raise ChainOfThoughtRejectedError(
            f"{field} must not expose or claim to expose private chain-of-thought"
        )


def disclaimer_for(kind: ClaimKind) -> str:
    if kind is ClaimKind.FORECAST_SCENARIO:
        return FORECAST_DISCLAIMER
    if kind is ClaimKind.SYNTHETIC_AUDIENCE_HYPOTHESIS:
        return SYNTHETIC_AUDIENCE_DISCLAIMER
    return ""


@dataclass(frozen=True, slots=True)
class MethodProvenance:
    """Model/method provenance attached to a consequential claim."""

    provider: str
    model: str
    model_version: str
    prompt_version: str
    policy_version: str
    timestamp: str
    prompt_id: str = ""
    method: str = ""
    adapter_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "provider": self.provider,
            "model": self.model,
            "model_version": self.model_version,
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "policy_version": self.policy_version,
            "timestamp": self.timestamp,
            "method": self.method,
            "adapter_id": self.adapter_id,
        }
        reject_chain_of_thought(payload, field="method_provenance")
        assert "chain_of_thought" not in payload
        return payload

    @classmethod
    def from_mapping(cls, value: MethodProvenance | Mapping[str, Any]) -> MethodProvenance:
        if isinstance(value, MethodProvenance):
            reject_chain_of_thought(value.to_dict(), field="method_provenance")
            return value
        reject_chain_of_thought(dict(value), field="method_provenance")
        adapter = value.get("adapter_id")
        return cls(
            provider=str(value["provider"]),
            model=str(value["model"]),
            model_version=str(value["model_version"]),
            prompt_version=str(value["prompt_version"]),
            policy_version=str(value["policy_version"]),
            timestamp=str(value["timestamp"]),
            prompt_id=str(value.get("prompt_id") or ""),
            method=str(value.get("method") or ""),
            adapter_id=str(adapter) if adapter is not None else None,
        )


@dataclass(frozen=True, slots=True)
class InputLineage:
    source_ids: tuple[str, ...] = ()
    revision_ids: tuple[str, ...] = ()
    artifact_version_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_ids": list(self.source_ids),
            "revision_ids": list(self.revision_ids),
            "artifact_version_ids": list(self.artifact_version_ids),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> InputLineage:
        return cls(
            source_ids=tuple(str(item) for item in data.get("source_ids", ())),
            revision_ids=tuple(str(item) for item in data.get("revision_ids", ())),
            artifact_version_ids=tuple(
                str(item) for item in data.get("artifact_version_ids", ())
            ),
        )


@dataclass(frozen=True, slots=True)
class CitationInput:
    source_id: str
    excerpt_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "excerpt_summary": self.excerpt_summary}


@dataclass(frozen=True, slots=True)
class BundleValidation:
    bundle_id: str
    state: HumanValidationState
    actor_id: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "state": self.state.value,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BundleValidation:
        return cls(
            bundle_id=str(data["bundle_id"]),
            state=HumanValidationState(str(data["state"])),
            actor_id=str(data["actor_id"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class StoredEvidenceBundle:
    """Module record wrapping the constitutional EvidenceBundle plus lineage."""

    bundle: EvidenceBundle
    project_id: str
    claim_kind: ClaimKind
    method_provenance: MethodProvenance
    lineage: InputLineage
    uncertainty: str
    rights_license: str
    epistemic_disclaimer: str
    created_by: str
    validated_by: str | None = None
    validated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "bundle": self.bundle.to_dict(),
            "project_id": self.project_id,
            "claim_kind": self.claim_kind.value,
            "method_provenance": self.method_provenance.to_dict(),
            "lineage": self.lineage.to_dict(),
            "uncertainty": self.uncertainty,
            "rights_license": self.rights_license,
            "epistemic_disclaimer": self.epistemic_disclaimer,
            "created_by": self.created_by,
            "validated_by": self.validated_by,
            "validated_at": self.validated_at,
        }
        reject_chain_of_thought(payload, field="evidence_bundle")
        assert "chain_of_thought" not in payload
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StoredEvidenceBundle:
        reject_chain_of_thought(dict(data), field="evidence_bundle")
        bundle_payload = data["bundle"]
        provenance_payload = data["method_provenance"]
        if not isinstance(bundle_payload, Mapping):
            raise ValueError("evidence bundle payload is not an object")
        if not isinstance(provenance_payload, Mapping):
            raise ValueError("method provenance payload is not an object")
        return cls(
            bundle=EvidenceBundle.from_dict(dict(bundle_payload)),
            project_id=str(data["project_id"]),
            claim_kind=ClaimKind(str(data["claim_kind"])),
            method_provenance=MethodProvenance.from_mapping(provenance_payload),
            lineage=InputLineage.from_dict(dict(data.get("lineage") or {})),
            uncertainty=str(data.get("uncertainty") or "unspecified"),
            rights_license=str(data.get("rights_license") or ""),
            epistemic_disclaimer=str(data.get("epistemic_disclaimer") or ""),
            created_by=str(data["created_by"]),
            validated_by=str(data["validated_by"]) if data.get("validated_by") else None,
            validated_at=str(data["validated_at"]) if data.get("validated_at") else None,
        )

    def public_view(self) -> dict[str, Any]:
        """Creator-facing explanation. Never includes private chain-of-thought."""

        payload = {
            "id": self.bundle.id,
            "claim": self.bundle.claim,
            "claim_kind": self.claim_kind.value,
            "recommendation": self.bundle.claim,
            "cited_node_ids": list(self.bundle.cited_node_ids),
            "cited_sources": [item.to_dict() for item in self.bundle.cited_sources],
            "method_summary": self.bundle.method_summary,
            "model": self.method_provenance.model,
            "model_version": self.method_provenance.model_version,
            "provider": self.method_provenance.provider,
            "prompt_version": self.method_provenance.prompt_version,
            "policy_version": self.method_provenance.policy_version,
            "assumptions": list(self.bundle.assumptions),
            "confidence": self.bundle.confidence,
            "uncertainty": self.uncertainty,
            "alternatives": list(self.bundle.alternatives),
            "counter_evidence": list(self.bundle.counter_evidence),
            "sensitivity": self.bundle.sensitivity,
            "rights_license": self.rights_license,
            "timestamp": self.bundle.created_at,
            "human_validation_state": self.bundle.human_validation_state.value,
            "validated_by": self.validated_by,
            "validated_at": self.validated_at,
            "input_lineage": self.lineage.to_dict(),
            "epistemic_disclaimer": self.epistemic_disclaimer,
        }
        reject_chain_of_thought(payload, field="public_view")
        assert "chain_of_thought" not in payload
        return payload


@dataclass(frozen=True, slots=True)
class ExportDisclosure:
    bundle_id: str
    project_id: str
    claim: str
    claim_kind: ClaimKind
    cited_sources: tuple[CitedSource, ...]
    cited_node_ids: tuple[str, ...]
    method_summary: str
    method_provenance: MethodProvenance
    assumptions: tuple[str, ...]
    confidence: float
    uncertainty: str
    alternatives: tuple[str, ...]
    counter_evidence: tuple[str, ...]
    sensitivity: str | None
    rights_license: str
    source_disclosures: tuple[dict[str, Any], ...]
    lineage: InputLineage
    human_validation_state: HumanValidationState
    validated_by: str | None
    validated_at: str | None
    epistemic_disclaimer: str
    exported_at: str
    exported_by: str

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "bundle_id": self.bundle_id,
            "project_id": self.project_id,
            "claim": self.claim,
            "claim_kind": self.claim_kind.value,
            "cited_sources": [item.to_dict() for item in self.cited_sources],
            "cited_node_ids": list(self.cited_node_ids),
            "method_summary": self.method_summary,
            "method_provenance": self.method_provenance.to_dict(),
            "assumptions": list(self.assumptions),
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "alternatives": list(self.alternatives),
            "counter_evidence": list(self.counter_evidence),
            "sensitivity": self.sensitivity,
            "rights_license": self.rights_license,
            "source_disclosures": list(self.source_disclosures),
            "lineage": self.lineage.to_dict(),
            "human_validation_state": self.human_validation_state.value,
            "validated_by": self.validated_by,
            "validated_at": self.validated_at,
            "epistemic_disclaimer": self.epistemic_disclaimer,
            "exported_at": self.exported_at,
            "exported_by": self.exported_by,
        }
        reject_chain_of_thought(payload, field="export_disclosure")
        assert "chain_of_thought" not in payload
        return payload


__all__ = [
    "CHAIN_OF_THOUGHT_MARKERS",
    "FORECAST_DISCLAIMER",
    "SYNTHETIC_AUDIENCE_DISCLAIMER",
    "BundleValidation",
    "CitationInput",
    "ClaimKind",
    "ExportDisclosure",
    "InputLineage",
    "MethodProvenance",
    "StoredEvidenceBundle",
    "contains_chain_of_thought",
    "disclaimer_for",
    "reject_chain_of_thought",
]
