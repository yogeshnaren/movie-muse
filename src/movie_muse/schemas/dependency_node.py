"""DependencyNode — one node in the product-derived-data dependency graph.

Architecture §7: distinct from ``dependency_dag.yaml`` (the work-package
graph). Every derived node records input IDs/hashes, code version, schema
version, model/provider version, prompt/template version, rights snapshot,
and produced-at time, so an accepted ChangeSet can compute the minimal
invalidation frontier and mark the dependent closure stale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from movie_muse.schemas.serialization import dataclass_from_dict, dataclass_to_dict, sealed


@sealed
@dataclass(frozen=True, slots=True)
class DependencyNode:
    SCHEMA_NAME: ClassVar[str] = "dependency_node"

    id: str
    project_id: str
    node_type: str
    input_ids: tuple[str, ...]
    input_hashes: tuple[str, ...]
    code_version: str
    produced_at: str
    schema_version: str = "1.0"
    model_version: str | None = None
    prompt_template_version: str | None = None
    rights_snapshot_id: str | None = None
    is_stale: bool = False

    def __post_init__(self) -> None:
        if len(self.input_ids) != len(self.input_hashes):
            raise ValueError("input_ids and input_hashes must be the same length and order")

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DependencyNode:
        return dataclass_from_dict(
            cls, data, converters={"input_ids": tuple, "input_hashes": tuple}
        )
