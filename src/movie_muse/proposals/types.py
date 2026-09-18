"""Proposal envelopes, reviews, and accept results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.schemas.api import ChangeSet, ImpactSummary, Proposal, ProposalStatus


class ProposalOrigin(str, Enum):
    HUMAN = "human"
    AI = "ai"
    COLLABORATION = "collaboration"


@dataclass(frozen=True, slots=True)
class ProposalEnvelope:
    proposal: Proposal
    origin: ProposalOrigin
    alternative_change_sets: tuple[ChangeSet, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    remainder_of: str | None = None
    accepted_operation_ids: tuple[str, ...] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal": self.proposal.to_dict(),
            "origin": self.origin.value,
            "alternative_change_sets": [item.to_dict() for item in self.alternative_change_sets],
            "evidence_ids": list(self.evidence_ids),
            "remainder_of": self.remainder_of,
            "accepted_operation_ids": (
                list(self.accepted_operation_ids) if self.accepted_operation_ids is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProposalEnvelope:
        remainder = data.get("remainder_of")
        accepted = data.get("accepted_operation_ids")
        return cls(
            proposal=Proposal.from_dict(dict(data["proposal"])),
            origin=ProposalOrigin(str(data["origin"])),
            alternative_change_sets=tuple(
                ChangeSet.from_dict(item) for item in data.get("alternative_change_sets", ())
            ),
            evidence_ids=tuple(str(item) for item in data.get("evidence_ids", ())),
            remainder_of=str(remainder) if remainder is not None else None,
            accepted_operation_ids=(
                tuple(str(item) for item in accepted) if accepted is not None else None
            ),
        )


@dataclass(frozen=True, slots=True)
class ProposalReview:
    envelope: ProposalEnvelope
    stale: bool
    head_revision_id: str

    @property
    def proposal(self) -> Proposal:
        return self.envelope.proposal

    @property
    def impact(self) -> ImpactSummary:
        return self.proposal.impact

    @property
    def status(self) -> ProposalStatus:
        return self.proposal.status


@dataclass(frozen=True, slots=True)
class AcceptResult:
    proposal: Proposal
    revision_id: str
    audit_id: str
    remainder: Proposal | None = None
    invalidated_node_ids: tuple[str, ...] = ()
