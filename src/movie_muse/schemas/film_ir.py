"""FilmIR — normalized entities, scenes, events, mentions, chronology, locations,
props, and cast: level 2 of the Film Graph (architecture §3.5).

FilmIR entries are ``StructuralFact``-level: deterministically derived from a
screenplay revision by a reducer/extractor, never authored directly and
never a probabilistic claim. The compiler/extraction pipeline is MM-018's
scope; this module defines only the versioned shape.
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


class FilmIrEntityKind(str, Enum):
    CHARACTER = "character"
    LOCATION = "location"
    PROP = "prop"
    SCENE = "scene"
    EVENT = "event"


@sealed
@dataclass(frozen=True, slots=True)
class FilmIrEntity:
    id: str
    kind: FilmIrEntityKind
    canonical_name: str
    scene_ids: tuple[str, ...] = ()
    mention_block_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FilmIrEntity:
        return dataclass_from_dict(
            cls,
            data,
            converters={
                "kind": FilmIrEntityKind,
                "scene_ids": tuple,
                "mention_block_ids": tuple,
            },
        )


@sealed
@dataclass(frozen=True, slots=True)
class FilmIR:
    SCHEMA_NAME: ClassVar[str] = "film_ir"

    id: str
    project_id: str
    source_revision_id: str
    extractor_version: str
    computed_at: str
    entities: tuple[FilmIrEntity, ...] = ()
    scene_order: tuple[str, ...] = ()
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FilmIR:
        return dataclass_from_dict(
            cls,
            data,
            converters={
                "entities": tuple_of(FilmIrEntity.from_dict),
                "scene_order": tuple,
            },
        )
