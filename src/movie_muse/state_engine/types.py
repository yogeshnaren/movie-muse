"""Typed state transitions, facts, contradictions, and query snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.schemas.api import EpistemicLevel


class StateDimension(str, Enum):
    KNOWLEDGE = "knowledge"
    SUSPICION = "suspicion"
    CONFIRMATION = "confirmation"
    BELIEF = "belief"
    SECOND_ORDER_BELIEF = "second_order_belief"
    MISUNDERSTANDING = "misunderstanding"
    RELATIONSHIP = "relationship"
    OBJECTIVE = "objective"
    POSSESSION = "possession"
    INJURY = "injury"
    WARDROBE = "wardrobe"
    LOCATION = "location"
    SECRET = "secret"
    ALLEGIANCE = "allegiance"
    WORLD = "world"


class Polarity(str, Enum):
    UNKNOWN = "unknown"
    SUSPECTS = "suspects"
    BELIEVES = "believes"
    KNOWS = "knows"
    CONFIRMED = "confirmed"
    DENIED = "denied"


AUTHORITY_RANK = {
    EpistemicLevel.AUTHORED: 0,
    EpistemicLevel.STRUCTURAL: 1,
    EpistemicLevel.INFERRED: 2,
    EpistemicLevel.OPERATIONAL: 3,
    EpistemicLevel.SCENARIO: 4,
}

INCOMPATIBLE_POLARITIES = frozenset(
    {
        (Polarity.KNOWS, Polarity.DENIED),
        (Polarity.DENIED, Polarity.KNOWS),
        (Polarity.CONFIRMED, Polarity.DENIED),
        (Polarity.DENIED, Polarity.CONFIRMED),
        (Polarity.BELIEVES, Polarity.DENIED),
        (Polarity.DENIED, Polarity.BELIEVES),
    }
)


@dataclass(frozen=True, slots=True)
class StateTransition:
    subject_id: str
    dimension: StateDimension
    attribute: str
    value: str
    polarity: Polarity
    scene_id: str
    source_kind: EpistemicLevel
    source_id: str
    evidence_ids: tuple[str, ...] = ()
    about_subject_id: str | None = None
    subject_name: str | None = None

    def key(self) -> tuple[str, str, str, str]:
        return (
            self.subject_id,
            self.dimension.value,
            self.attribute,
            self.about_subject_id or "",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "dimension": self.dimension.value,
            "attribute": self.attribute,
            "value": self.value,
            "polarity": self.polarity.value,
            "scene_id": self.scene_id,
            "source_kind": self.source_kind.value,
            "source_id": self.source_id,
            "evidence_ids": list(self.evidence_ids),
            "about_subject_id": self.about_subject_id,
            "subject_name": self.subject_name,
        }


@dataclass(frozen=True, slots=True)
class StateFact:
    id: str
    subject_id: str
    dimension: StateDimension
    attribute: str
    value: str
    polarity: Polarity
    valid_from_scene_id: str
    source_kind: EpistemicLevel
    source_id: str
    evidence_ids: tuple[str, ...]
    revision_id: str
    about_subject_id: str | None = None
    subject_name: str | None = None
    valid_until_scene_id: str | None = None

    def key(self) -> tuple[str, str, str, str]:
        return (
            self.subject_id,
            self.dimension.value,
            self.attribute,
            self.about_subject_id or "",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "dimension": self.dimension.value,
            "attribute": self.attribute,
            "value": self.value,
            "polarity": self.polarity.value,
            "valid_from_scene_id": self.valid_from_scene_id,
            "valid_until_scene_id": self.valid_until_scene_id,
            "source_kind": self.source_kind.value,
            "source_id": self.source_id,
            "evidence_ids": list(self.evidence_ids),
            "revision_id": self.revision_id,
            "about_subject_id": self.about_subject_id,
            "subject_name": self.subject_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateFact:
        until = data.get("valid_until_scene_id")
        about = data.get("about_subject_id")
        name = data.get("subject_name")
        return cls(
            id=str(data["id"]),
            subject_id=str(data["subject_id"]),
            dimension=StateDimension(str(data["dimension"])),
            attribute=str(data["attribute"]),
            value=str(data["value"]),
            polarity=Polarity(str(data["polarity"])),
            valid_from_scene_id=str(data["valid_from_scene_id"]),
            source_kind=EpistemicLevel(str(data["source_kind"])),
            source_id=str(data["source_id"]),
            evidence_ids=tuple(str(item) for item in data.get("evidence_ids", ())),
            revision_id=str(data["revision_id"]),
            about_subject_id=str(about) if about is not None else None,
            subject_name=str(name) if name is not None else None,
            valid_until_scene_id=str(until) if until is not None else None,
        )


@dataclass(frozen=True, slots=True)
class Contradiction:
    id: str
    scene_id: str
    subject_id: str
    dimension: StateDimension
    attribute: str
    left_fact_id: str
    right_fact_id: str
    evidence_ids: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scene_id": self.scene_id,
            "subject_id": self.subject_id,
            "dimension": self.dimension.value,
            "attribute": self.attribute,
            "left_fact_id": self.left_fact_id,
            "right_fact_id": self.right_fact_id,
            "evidence_ids": list(self.evidence_ids),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Contradiction:
        return cls(
            id=str(data["id"]),
            scene_id=str(data["scene_id"]),
            subject_id=str(data["subject_id"]),
            dimension=StateDimension(str(data["dimension"])),
            attribute=str(data["attribute"]),
            left_fact_id=str(data["left_fact_id"]),
            right_fact_id=str(data["right_fact_id"]),
            evidence_ids=tuple(str(item) for item in data.get("evidence_ids", ())),
            reason=str(data["reason"]),
        )


@dataclass(frozen=True, slots=True)
class HumanCorrection:
    id: str
    transition: StateTransition
    actor_id: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "transition": self.transition.to_dict(),
            "actor_id": self.actor_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HumanCorrection:
        raw = dict(data["transition"])
        return cls(
            id=str(data["id"]),
            transition=StateTransition(
                subject_id=str(raw["subject_id"]),
                dimension=StateDimension(str(raw["dimension"])),
                attribute=str(raw["attribute"]),
                value=str(raw["value"]),
                polarity=Polarity(str(raw["polarity"])),
                scene_id=str(raw["scene_id"]),
                source_kind=EpistemicLevel(str(raw["source_kind"])),
                source_id=str(raw["source_id"]),
                evidence_ids=tuple(str(item) for item in raw.get("evidence_ids", ())),
                about_subject_id=(
                    str(raw["about_subject_id"])
                    if raw.get("about_subject_id") is not None
                    else None
                ),
                subject_name=(
                    str(raw["subject_name"]) if raw.get("subject_name") is not None else None
                ),
            ),
            actor_id=str(data["actor_id"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    scene_id: str
    revision_id: str
    facts: tuple[StateFact, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "revision_id": self.revision_id,
            "facts": [fact.to_dict() for fact in self.facts],
        }


@dataclass(frozen=True, slots=True)
class Reduction:
    revision_id: str
    facts: tuple[StateFact, ...]
    contradictions: tuple[Contradiction, ...]
    misunderstandings: tuple[StateFact, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "facts": [fact.to_dict() for fact in self.facts],
            "contradictions": [item.to_dict() for item in self.contradictions],
            "misunderstandings": [fact.to_dict() for fact in self.misunderstandings],
        }
