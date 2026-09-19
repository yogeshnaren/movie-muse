"""CreativeIntentIR — creator-stated intended audience experience and invariants.

Architecture §3.5: scoped at film, sequence, scene, or beat level; records
source role, lock state, revision, and provenance. This is level 4 of the
Film Graph, strictly distinct from FilmIR's deterministic level 2 facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from movie_muse.schemas.serialization import dataclass_from_dict, dataclass_to_dict, sealed


class IntentScope(str, Enum):
    FILM = "film"
    SEQUENCE = "sequence"
    SCENE = "scene"
    BEAT = "beat"


class IntentSourceRole(str, Enum):
    WRITER = "writer"
    DIRECTOR = "director"
    CINEMATOGRAPHER = "cinematographer"
    OTHER_CRAFT = "other_craft"
    INFERRED = "inferred"


@sealed
@dataclass(frozen=True, slots=True)
class CreativeIntentIR:
    SCHEMA_NAME: ClassVar[str] = "creative_intent_ir"

    id: str
    project_id: str
    scope: IntentScope
    scope_target_id: str
    statement: str
    source_role: IntentSourceRole
    is_locked: bool
    revision_id: str
    created_at: str
    exceptions: tuple[str, ...] = ()
    anti_rules: tuple[str, ...] = ()
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if self.source_role == IntentSourceRole.INFERRED and self.is_locked:
            raise ValueError("an inferred creative intent cannot be locked without human authorization")

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeIntentIR:
        return dataclass_from_dict(
            cls,
            data,
            converters={
                "scope": IntentScope,
                "source_role": IntentSourceRole,
                "exceptions": tuple,
                "anti_rules": tuple,
            },
        )
