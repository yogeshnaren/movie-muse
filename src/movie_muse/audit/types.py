"""Append-only audit records with integrity hashes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


def compute_audit_hash(
    *,
    sequence: int,
    actor_id: str,
    effective_principal_id: str,
    operation: str,
    object_kind: str,
    object_id: str,
    before_revision_id: str | None,
    after_revision_id: str | None,
    policy_decision: str,
    created_at: str,
    correlation_id: str,
    acl_epoch: int,
    reason: str,
    previous_hash: str | None,
    schema_version: str,
) -> str:
    canonical = json.dumps(
        {
            "acl_epoch": acl_epoch,
            "actor_id": actor_id,
            "after_revision_id": after_revision_id,
            "before_revision_id": before_revision_id,
            "correlation_id": correlation_id,
            "created_at": created_at,
            "effective_principal_id": effective_principal_id,
            "object_id": object_id,
            "object_kind": object_kind,
            "operation": operation,
            "policy_decision": policy_decision,
            "previous_hash": previous_hash,
            "reason": reason,
            "schema_version": schema_version,
            "sequence": sequence,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AuditRecord:
    id: str
    sequence: int
    actor_id: str
    effective_principal_id: str
    operation: str
    object_kind: str
    object_id: str
    policy_decision: PolicyDecision
    created_at: str
    correlation_id: str
    integrity_hash: str
    acl_epoch: int
    reason: str
    before_revision_id: str | None = None
    after_revision_id: str | None = None
    previous_hash: str | None = None
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sequence": self.sequence,
            "actor_id": self.actor_id,
            "effective_principal_id": self.effective_principal_id,
            "operation": self.operation,
            "object_kind": self.object_kind,
            "object_id": self.object_id,
            "policy_decision": self.policy_decision.value,
            "created_at": self.created_at,
            "correlation_id": self.correlation_id,
            "integrity_hash": self.integrity_hash,
            "acl_epoch": self.acl_epoch,
            "reason": self.reason,
            "before_revision_id": self.before_revision_id,
            "after_revision_id": self.after_revision_id,
            "previous_hash": self.previous_hash,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditRecord:
        return cls(
            id=str(data["id"]),
            sequence=int(data["sequence"]),
            actor_id=str(data["actor_id"]),
            effective_principal_id=str(data["effective_principal_id"]),
            operation=str(data["operation"]),
            object_kind=str(data["object_kind"]),
            object_id=str(data["object_id"]),
            policy_decision=PolicyDecision(str(data["policy_decision"])),
            created_at=str(data["created_at"]),
            correlation_id=str(data["correlation_id"]),
            integrity_hash=str(data["integrity_hash"]),
            acl_epoch=int(data["acl_epoch"]),
            reason=str(data["reason"]),
            before_revision_id=str(data["before_revision_id"]) if data.get("before_revision_id") else None,
            after_revision_id=str(data["after_revision_id"]) if data.get("after_revision_id") else None,
            previous_hash=str(data["previous_hash"]) if data.get("previous_hash") else None,
            schema_version=str(data.get("schema_version", "1.0")),
        )

    def expected_hash(self) -> str:
        return compute_audit_hash(
            sequence=self.sequence,
            actor_id=self.actor_id,
            effective_principal_id=self.effective_principal_id,
            operation=self.operation,
            object_kind=self.object_kind,
            object_id=self.object_id,
            before_revision_id=self.before_revision_id,
            after_revision_id=self.after_revision_id,
            policy_decision=self.policy_decision.value,
            created_at=self.created_at,
            correlation_id=self.correlation_id,
            acl_epoch=self.acl_epoch,
            reason=self.reason,
            previous_hash=self.previous_hash,
            schema_version=self.schema_version,
        )
