"""Append-only audit authority. Records cannot be updated or deleted."""

from __future__ import annotations

from typing import Any

from movie_muse.audit.errors import AuditImmutableError, AuditIntegrityError
from movie_muse.audit.index import (
    clone_index,
    commit_index,
    empty_index,
    load_index,
    load_json_blob,
    put_json_blob,
)
from movie_muse.audit.types import AuditRecord, PolicyDecision, compute_audit_hash
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.schemas.api import new_ulid


class AuditLog:
    """Local append-only audit log. Replay/list order is the append sequence."""

    def __init__(self, workspace: LocalWorkspace) -> None:
        self.workspace = workspace

    def append(
        self,
        *,
        actor_id: str,
        effective_principal_id: str,
        operation: str,
        object_kind: str,
        object_id: str,
        policy_decision: PolicyDecision | str,
        acl_epoch: int,
        reason: str,
        correlation_id: str | None = None,
        before_revision_id: str | None = None,
        after_revision_id: str | None = None,
        created_at: str | None = None,
    ) -> AuditRecord:
        index = clone_index(self._ensure_index())
        sequence = int(index["next_sequence"])
        previous_hash = str(index["tail_hash"]) if index["tail_hash"] else None
        decision = (
            policy_decision
            if isinstance(policy_decision, PolicyDecision)
            else PolicyDecision(str(policy_decision))
        )
        stamp = created_at or utc_now()
        correlation = correlation_id or new_ulid()
        record_id = f"aud_{new_ulid()}"
        integrity = compute_audit_hash(
            sequence=sequence,
            actor_id=actor_id,
            effective_principal_id=effective_principal_id,
            operation=operation,
            object_kind=object_kind,
            object_id=object_id,
            before_revision_id=before_revision_id,
            after_revision_id=after_revision_id,
            policy_decision=decision.value,
            created_at=stamp,
            correlation_id=correlation,
            acl_epoch=acl_epoch,
            reason=reason,
            previous_hash=previous_hash,
            schema_version="1.0",
        )
        record = AuditRecord(
            id=record_id,
            sequence=sequence,
            actor_id=actor_id,
            effective_principal_id=effective_principal_id,
            operation=operation,
            object_kind=object_kind,
            object_id=object_id,
            policy_decision=decision,
            created_at=stamp,
            correlation_id=correlation,
            integrity_hash=integrity,
            acl_epoch=acl_epoch,
            reason=reason,
            before_revision_id=before_revision_id,
            after_revision_id=after_revision_id,
            previous_hash=previous_hash,
        )
        digest = put_json_blob(self.workspace, record.to_dict())
        index["record_ids"].append(record.id)
        index["record_digests"][record.id] = digest
        index["tail_hash"] = integrity
        index["next_sequence"] = sequence + 1
        commit_index(self.workspace, index)
        return record

    def get(self, record_id: str) -> AuditRecord:
        index = self._ensure_index()
        digest = index["record_digests"].get(record_id)
        if digest is None:
            raise AuditIntegrityError(f"unknown audit record: {record_id}")
        record = AuditRecord.from_dict(load_json_blob(self.workspace, str(digest)))
        self._assert_integrity(record)
        return record

    def list_records(self) -> tuple[AuditRecord, ...]:
        """Deterministic replay order: append sequence, never wall-clock sort."""

        index = self._ensure_index()
        records = [self.get(record_id) for record_id in index["record_ids"]]
        return tuple(records)

    def replay(self) -> tuple[AuditRecord, ...]:
        records = self.list_records()
        previous: str | None = None
        for record in records:
            if record.previous_hash != previous:
                raise AuditIntegrityError(f"audit chain break at {record.id}")
            self._assert_integrity(record)
            previous = record.integrity_hash
        return records

    def update(self, record_id: str, **_changes: object) -> None:
        raise AuditImmutableError(f"audit records cannot be updated: {record_id}")

    def delete(self, record_id: str) -> None:
        raise AuditImmutableError(f"audit records cannot be deleted: {record_id}")

    def _ensure_index(self) -> dict[str, Any]:
        loaded = load_index(self.workspace)
        if loaded is not None:
            return loaded
        return empty_index()

    @staticmethod
    def _assert_integrity(record: AuditRecord) -> None:
        expected = record.expected_hash()
        if expected != record.integrity_hash:
            raise AuditIntegrityError(
                f"integrity_hash does not match recomputed hash for {record.id}"
            )
