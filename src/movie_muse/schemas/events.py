"""ProjectEvent — immutable command -> event canonical history.

Architecture §3.3: every accepted canonical mutation emits an immutable
``ProjectEvent`` carrying project, branch, base/result revision, actor,
command/operation id, schema version, causal/correlation ids, and an
integrity hash. This is the schema/type only; the append-only store and
replay machinery belong to MM-005/MM-011.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, ClassVar

from movie_muse.schemas.serialization import (
    dataclass_from_dict,
    dataclass_to_dict,
    freeze_json,
    to_json_dict,
)

#: Closed catalogue of canonical event types named in architecture §3.3.
#: Additional event types are an additive schema change (new enum member),
#: never a free-form string, so downstream consumers cannot silently accept
#: unmodeled event semantics.
EVENT_TYPES: frozenset[str] = frozenset(
    {
        "ScreenplayPatchAccepted",
        "CharacterIntentLocked",
        "SceneMoved",
        "ProductionRequirementConfirmed",
        "DepartmentDecisionConfirmed",
        "AssumptionChanged",
    }
)


def compute_integrity_hash(
    *,
    project_id: str,
    branch_id: str,
    base_revision_id: str | None,
    result_revision_id: str,
    actor_id: str,
    effective_principal_id: str,
    command_id: str,
    operation_id: str,
    event_type: str,
    schema_version: str,
    causal_id: str | None,
    correlation_id: str,
    payload: dict[str, Any],
) -> str:
    canonical = json.dumps(
        {
            "project_id": project_id,
            "branch_id": branch_id,
            "base_revision_id": base_revision_id,
            "result_revision_id": result_revision_id,
            "actor_id": actor_id,
            "effective_principal_id": effective_principal_id,
            "command_id": command_id,
            "operation_id": operation_id,
            "event_type": event_type,
            "schema_version": schema_version,
            "causal_id": causal_id,
            "correlation_id": correlation_id,
            "payload": to_json_dict(payload),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ProjectEvent:
    SCHEMA_NAME: ClassVar[str] = "project_event"

    id: str
    project_id: str
    branch_id: str
    result_revision_id: str
    actor_id: str
    effective_principal_id: str
    command_id: str
    operation_id: str
    event_type: str
    created_at: str
    correlation_id: str
    integrity_hash: str
    base_revision_id: str | None = None
    causal_id: str | None = None
    payload: dict[str, Any] | None = None
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", freeze_json(self.payload) if self.payload is not None else None)
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event_type: {self.event_type!r}")
        expected = compute_integrity_hash(
            project_id=self.project_id,
            branch_id=self.branch_id,
            base_revision_id=self.base_revision_id,
            result_revision_id=self.result_revision_id,
            actor_id=self.actor_id,
            effective_principal_id=self.effective_principal_id,
            command_id=self.command_id,
            operation_id=self.operation_id,
            event_type=self.event_type,
            schema_version=self.schema_version,
            causal_id=self.causal_id,
            correlation_id=self.correlation_id,
            payload=self.payload or {},
        )
        if expected != self.integrity_hash:
            raise ValueError("integrity_hash does not match recomputed hash; event is not trustworthy")

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectEvent:
        return dataclass_from_dict(cls, data)
