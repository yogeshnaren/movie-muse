"""CollaborationEvent — durable record from Room/meeting/live-collaboration capture.

Architecture §11: transcripts/notes/integrations/research produce candidate
records (idea, decision, question, assignment, research request, character
fact, scene proposal, rejected idea) that require review before promotion
into project memory or canon ("Room Harvest").
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from movie_muse.schemas.serialization import dataclass_from_dict, dataclass_to_dict


class CollaborationRecordKind(str, Enum):
    IDEA = "idea"
    DECISION = "decision"
    QUESTION = "question"
    ASSIGNMENT = "assignment"
    RESEARCH_REQUEST = "research_request"
    CHARACTER_FACT = "character_fact"
    SCENE_PROPOSAL = "scene_proposal"
    REJECTED_IDEA = "rejected_idea"


class PromotionState(str, Enum):
    CAPTURED = "captured"
    UNDER_REVIEW = "under_review"
    PROMOTED = "promoted"
    DISCARDED = "discarded"


@dataclass(frozen=True, slots=True)
class CollaborationEvent:
    SCHEMA_NAME: ClassVar[str] = "collaboration_event"

    id: str
    project_id: str
    source: str
    record_kind: CollaborationRecordKind
    summary: str
    captured_at: str
    speaker_actor_id: str | None = None
    promotion_state: PromotionState = PromotionState.CAPTURED
    promoted_project_memory_id: str | None = None
    schema_version: str = "1.1"

    def __post_init__(self) -> None:
        if self.promotion_state == PromotionState.PROMOTED and not self.promoted_project_memory_id:
            raise ValueError("promoted collaboration events must reference their project_memory id")

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CollaborationEvent:
        return dataclass_from_dict(
            cls,
            data,
            converters={
                "record_kind": CollaborationRecordKind,
                "promotion_state": PromotionState,
            },
        )
