"""ProjectMemory — reviewed capture promoted from Room Harvest or manual entry.

Architecture §11: candidate records require review before promotion into
project memory or canon; provenance is retained through that promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from movie_muse.schemas.serialization import dataclass_from_dict, dataclass_to_dict, sealed


class ProjectMemoryKind(str, Enum):
    DECISION = "decision"
    FACT = "fact"
    ASSIGNMENT = "assignment"
    RESEARCH_NOTE = "research_note"


@sealed
@dataclass(frozen=True, slots=True)
class ProjectMemory:
    SCHEMA_NAME: ClassVar[str] = "project_memory"

    id: str
    project_id: str
    kind: ProjectMemoryKind
    summary: str
    reviewed_by_actor_id: str
    reviewed_at: str
    source_collaboration_event_id: str | None = None
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectMemory:
        return dataclass_from_dict(cls, data, converters={"kind": ProjectMemoryKind})
