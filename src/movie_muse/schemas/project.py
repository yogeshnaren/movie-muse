"""Project — the top-level tenant/workspace container."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from movie_muse.schemas.serialization import dataclass_from_dict, dataclass_to_dict, sealed


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


@sealed
@dataclass(frozen=True, slots=True)
class Project:
    """A single canonical filmmaking project.

    ``ai_off`` preserves architecture §8's "AI is optional at project level"
    invariant: when true, no model-routed operation may run for this project
    regardless of capability-level settings.
    """

    SCHEMA_NAME: ClassVar[str] = "project"

    id: str
    organization_id: str
    title: str
    owner_actor_id: str
    created_at: str
    status: ProjectStatus = ProjectStatus.ACTIVE
    ai_off: bool = False
    canonical_branch_id: str | None = None
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        return dataclass_from_dict(cls, data, converters={"status": ProjectStatus})
