"""Immutable context request, budget, and assembled segments."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.identity.api import Principal
from movie_muse.retrieval.api import Citation
from movie_muse.rights.api import PermittedUse, SourceClassification, SourceValidationState
from movie_muse.schemas.api import (
    AuthoredFact,
    CreativeIntentIR,
    InferredClaim,
    OperationalAssumption,
    ProjectMemory,
    ScenarioOutput,
    StructuralFact,
)


class SegmentKind(str, Enum):
    REVISION = "revision"
    MEMORY = "memory"
    INTENT = "intent"
    AUTHORED_FACT = "authored_fact"
    STRUCTURAL_FACT = "structural_fact"
    INFERRED_CLAIM = "inferred_claim"
    OPERATIONAL_ASSUMPTION = "operational_assumption"
    SCENARIO_OUTPUT = "scenario_output"
    REFERENCE = "reference"


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """Tokenizer-independent limits. Counts are UTF-8 characters, bytes, segments."""

    max_chars: int = 8000
    max_bytes: int = 16000
    max_segments: int = 32

    def __post_init__(self) -> None:
        if self.max_chars < 1 or self.max_bytes < 1 or self.max_segments < 1:
            raise ValueError("context budget limits must be at least 1")


@dataclass(frozen=True, slots=True)
class BoundState:
    """Typed epistemic state bound to a tenant/branch before assembly."""

    project_id: str
    branch_id: str
    payload: (
        AuthoredFact
        | StructuralFact
        | InferredClaim
        | OperationalAssumption
        | ScenarioOutput
    )


@dataclass(frozen=True, slots=True)
class SegmentRights:
    classification: SourceClassification
    permitted_uses: tuple[PermittedUse, ...]
    rights_record_id: str | None
    validation_state: SourceValidationState
    license_summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification.value,
            "permitted_uses": [item.value for item in self.permitted_uses],
            "rights_record_id": self.rights_record_id,
            "validation_state": self.validation_state.value,
            "license_summary": self.license_summary,
        }


@dataclass(frozen=True, slots=True)
class Freshness:
    revision_id: str
    expected_revision_id: str | None
    as_of: str
    stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "expected_revision_id": self.expected_revision_id,
            "as_of": self.as_of,
            "stale": self.stale,
        }


@dataclass(frozen=True, slots=True)
class ContextSegment:
    id: str
    kind: SegmentKind
    text: str
    project_id: str
    branch_id: str
    revision_id: str
    source_id: str
    source_ids: tuple[str, ...]
    rights: SegmentRights
    citation: Citation | None
    freshness: Freshness
    redacted: bool
    untrusted: bool
    epistemic_level: str | None = None
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "text": self.text,
            "project_id": self.project_id,
            "branch_id": self.branch_id,
            "revision_id": self.revision_id,
            "source_id": self.source_id,
            "source_ids": list(self.source_ids),
            "rights": self.rights.to_dict(),
            "citation": None if self.citation is None else self.citation.to_dict(),
            "freshness": self.freshness.to_dict(),
            "redacted": self.redacted,
            "untrusted": self.untrusted,
            "epistemic_level": self.epistemic_level,
            "truncated": self.truncated,
        }


@dataclass(frozen=True, slots=True)
class ContextRequest:
    project_id: str
    branch_id: str
    principal: Principal
    acl_epoch: int
    expected_revision_id: str | None = None
    memories: tuple[ProjectMemory, ...] = ()
    intents: tuple[CreativeIntentIR, ...] = ()
    states: tuple[BoundState, ...] = ()
    retrieval_query: str | None = None
    budget: ContextBudget = ContextBudget()


@dataclass(frozen=True, slots=True)
class ContextBundle:
    id: str
    project_id: str
    branch_id: str
    revision_id: str
    assembled_at: str
    segments: tuple[ContextSegment, ...]
    char_count: int
    byte_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "branch_id": self.branch_id,
            "revision_id": self.revision_id,
            "assembled_at": self.assembled_at,
            "segments": [segment.to_dict() for segment in self.segments],
            "char_count": self.char_count,
            "byte_count": self.byte_count,
        }
