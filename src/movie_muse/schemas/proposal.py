"""Proposal — an immutable candidate ChangeSet against ``base_revision_id``.

Architecture §3.2: a Proposal carries intent, rationale summary,
semantic/continuity/production impacts, provenance, status, and a
revalidation record. If a proposal's base diverges from branch head,
acceptance must fail closed until rebase/revalidation succeeds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

from movie_muse.schemas.change_set import ChangeSet
from movie_muse.schemas.serialization import dataclass_from_dict, dataclass_to_dict


class ProposalStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class ImpactSummary:
    semantic: tuple[str, ...] = ()
    continuity: tuple[str, ...] = ()
    production: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImpactSummary:
        return dataclass_from_dict(
            cls,
            data,
            converters={"semantic": tuple, "continuity": tuple, "production": tuple},
        )


@dataclass(frozen=True, slots=True)
class RevalidationRecord:
    checked_at: str
    base_revision_id: str
    is_current: bool
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RevalidationRecord:
        return dataclass_from_dict(cls, data)


@dataclass(frozen=True, slots=True)
class Proposal:
    SCHEMA_NAME: ClassVar[str] = "proposal"

    id: str
    project_id: str
    change_set: ChangeSet
    base_revision_id: str
    intent: str
    rationale_summary: str
    provenance: str
    created_at: str
    status: ProposalStatus = ProposalStatus.PENDING
    impact: ImpactSummary = field(default_factory=ImpactSummary)
    revalidation: RevalidationRecord | None = None
    schema_version: str = "1.0"

    def validate(self) -> None:
        if self.change_set.base_revision_id != self.base_revision_id:
            raise ValueError(
                "proposal base_revision_id must match its change set's base_revision_id"
            )
        self.change_set.validate()

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Proposal:
        return dataclass_from_dict(
            cls,
            data,
            converters={
                "change_set": ChangeSet.from_dict,
                "status": ProposalStatus,
                "impact": ImpactSummary.from_dict,
                "revalidation": lambda v: RevalidationRecord.from_dict(v) if v is not None else None,
            },
        )
