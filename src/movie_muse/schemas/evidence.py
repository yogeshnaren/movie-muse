"""EvidenceBundle — provenance/uncertainty attached to every consequential claim.

Architecture §10: claim/recommendation, cited nodes and permitted sources,
method summary, model and version, assumptions, confidence/uncertainty,
alternatives, counter-evidence, sensitivity where relevant, rights/license,
timestamp, and human-validation state. MUST NOT expose private chain-of-thought.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from movie_muse.schemas.serialization import (
    dataclass_from_dict,
    dataclass_to_dict,
    sealed,
    tuple_of,
)


class HumanValidationState(str, Enum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


@sealed
@dataclass(frozen=True, slots=True)
class CitedSource:
    source_id: str
    rights_record_id: str
    excerpt_summary: str

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CitedSource:
        return dataclass_from_dict(cls, data)


@sealed
@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    SCHEMA_NAME: ClassVar[str] = "evidence_bundle"

    id: str
    claim: str
    method_summary: str
    model_id: str
    model_version: str
    confidence: float
    created_at: str
    cited_node_ids: tuple[str, ...] = ()
    cited_sources: tuple[CitedSource, ...] = ()
    assumptions: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    counter_evidence: tuple[str, ...] = ()
    sensitivity: str | None = None
    human_validation_state: HumanValidationState = HumanValidationState.UNREVIEWED
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be within [0.0, 1.0]")
        forbidden_markers = ("<thinking>", "chain-of-thought", "chain_of_thought")
        lowered = self.method_summary.lower()
        if any(marker in lowered for marker in forbidden_markers):
            raise ValueError("method_summary must not expose private chain-of-thought")

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceBundle:
        return dataclass_from_dict(
            cls,
            data,
            converters={
                "cited_node_ids": tuple,
                "cited_sources": tuple_of(CitedSource.from_dict),
                "assumptions": tuple,
                "alternatives": tuple,
                "counter_evidence": tuple,
                "human_validation_state": HumanValidationState,
            },
        )
