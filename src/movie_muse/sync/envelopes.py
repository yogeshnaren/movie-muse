"""Idempotent sync envelopes for local outbox/inbox."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from movie_muse.schemas.api import ScreenplayDocument

REQUIRED_FIELDS = (
    "project_id",
    "branch_id",
    "base_revision_id",
    "resulting_revision_id",
    "resulting_hash",
    "actor_id",
    "device_id",
    "operation_id",
    "schema_version",
    "acl_epoch",
)

ENVELOPE_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class SyncEnvelope:
    project_id: str
    branch_id: str
    base_revision_id: str
    resulting_revision_id: str
    resulting_hash: str
    actor_id: str
    device_id: str
    operation_id: str
    schema_version: str
    acl_epoch: int
    document: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "branch_id": self.branch_id,
            "base_revision_id": self.base_revision_id,
            "resulting_revision_id": self.resulting_revision_id,
            "resulting_hash": self.resulting_hash,
            "actor_id": self.actor_id,
            "device_id": self.device_id,
            "operation_id": self.operation_id,
            "schema_version": self.schema_version,
            "acl_epoch": self.acl_epoch,
            "document": self.document,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SyncEnvelope:
        missing = [field for field in REQUIRED_FIELDS if field not in data]
        if missing:
            raise ValueError(f"envelope missing fields: {missing}")
        document = data.get("document")
        if not isinstance(document, dict):
            raise ValueError("envelope.document must be an object")
        ScreenplayDocument.from_dict(document)
        return cls(
            project_id=str(data["project_id"]),
            branch_id=str(data["branch_id"]),
            base_revision_id=str(data["base_revision_id"]),
            resulting_revision_id=str(data["resulting_revision_id"]),
            resulting_hash=str(data["resulting_hash"]),
            actor_id=str(data["actor_id"]),
            device_id=str(data["device_id"]),
            operation_id=str(data["operation_id"]),
            schema_version=str(data["schema_version"]),
            acl_epoch=int(data["acl_epoch"]),
            document=dict(document),
        )


def cross_field_integrity_errors(
    envelope: SyncEnvelope,
    *,
    expected_project_id: str,
    expected_branch_id: str,
    expected_acl_epoch: int,
) -> tuple[str, ...]:
    """Fail-closed bindings required by architecture §4.

    Sync must verify that the envelope's project, branch, resulting revision,
    schema version, and ACL epoch match both the carried document and the
    local workspace. Hash agreement alone is not enough: a peer must not
    advance head to a revision id the document does not claim.
    """

    errors: list[str] = []
    document = envelope.document
    if envelope.resulting_revision_id != document.get("base_revision_id"):
        errors.append("resulting_revision_id")
    if envelope.base_revision_id == envelope.resulting_revision_id:
        errors.append("base_revision_id")
    if envelope.project_id != document.get("project_id"):
        errors.append("document.project_id")
    if envelope.project_id != expected_project_id:
        errors.append("project_id")
    if envelope.branch_id != expected_branch_id:
        errors.append("branch_id")
    if envelope.schema_version != ENVELOPE_SCHEMA_VERSION:
        errors.append("schema_version")
    if document.get("schema_version") != envelope.schema_version:
        errors.append("document.schema_version")
    if envelope.acl_epoch != expected_acl_epoch:
        errors.append("acl_epoch")
    return tuple(errors)
