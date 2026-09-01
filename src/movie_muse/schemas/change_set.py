"""ChangeSet — an ordered list of typed operations against an explicit base revision.

Architecture §3.2. ChangeSets are immutable once created; a new ChangeSet is
required to change course, never a mutation of an existing one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

from movie_muse.schemas.serialization import dataclass_from_dict, dataclass_to_dict, tuple_of


class OperationType(str, Enum):
    INSERT_BLOCK = "insert_block"
    DELETE_BLOCK = "delete_block"
    UPDATE_BLOCK = "update_block"
    MOVE_BLOCK = "move_block"
    INSERT_SCENE = "insert_scene"
    UPDATE_METADATA = "update_metadata"


@dataclass(frozen=True, slots=True)
class ChangeSetOperation:
    id: str
    order: int
    op_type: OperationType
    target_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChangeSetOperation:
        return dataclass_from_dict(cls, data, converters={"op_type": OperationType})


@dataclass(frozen=True, slots=True)
class ChangeSet:
    SCHEMA_NAME: ClassVar[str] = "change_set"

    id: str
    base_revision_id: str
    author_actor_id: str
    created_at: str
    operations: tuple[ChangeSetOperation, ...] = ()
    schema_version: str = "1.0"

    def validate(self) -> None:
        orders = [op.order for op in self.operations]
        if len(set(orders)) != len(orders):
            raise ValueError("changeset operations must have unique order values")
        if orders != sorted(orders):
            raise ValueError("changeset operations must be listed in ascending order")

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChangeSet:
        return dataclass_from_dict(
            cls, data, converters={"operations": tuple_of(ChangeSetOperation.from_dict)}
        )
