"""ProjectEvent construction using the closed ScreenplayPatchAccepted type."""

from __future__ import annotations

from typing import Any

from movie_muse.persistence.api import utc_now
from movie_muse.schemas.api import (
    ProjectEvent,
    compute_integrity_hash,
    new_id,
    new_ulid,
    to_json_dict,
)

EVENT_TYPE = "ScreenplayPatchAccepted"


def make_project_event(
    *,
    project_id: str,
    branch_id: str,
    result_revision_id: str,
    actor_id: str,
    payload: dict[str, Any],
    base_revision_id: str | None = None,
    command_id: str | None = None,
    operation_id: str | None = None,
    correlation_id: str | None = None,
    causal_id: str | None = None,
    created_at: str | None = None,
    effective_principal_id: str | None = None,
) -> ProjectEvent:
    command = command_id or new_ulid()
    operation = operation_id or new_ulid()
    created = created_at or utc_now()
    principal = effective_principal_id or actor_id
    correlation = correlation_id or command
    payload_dict = to_json_dict(payload) if payload else {}
    if not isinstance(payload_dict, dict):
        raise TypeError("event payload must serialize to an object")
    integrity_hash = compute_integrity_hash(
        project_id=project_id,
        branch_id=branch_id,
        base_revision_id=base_revision_id,
        result_revision_id=result_revision_id,
        actor_id=actor_id,
        effective_principal_id=principal,
        command_id=command,
        operation_id=operation,
        event_type=EVENT_TYPE,
        schema_version="1.0",
        causal_id=causal_id,
        correlation_id=correlation,
        payload=payload_dict,
    )
    return ProjectEvent(
        id=new_id("event"),
        project_id=project_id,
        branch_id=branch_id,
        result_revision_id=result_revision_id,
        actor_id=actor_id,
        effective_principal_id=principal,
        command_id=command,
        operation_id=operation,
        event_type=EVENT_TYPE,
        created_at=created,
        correlation_id=correlation,
        integrity_hash=integrity_hash,
        base_revision_id=base_revision_id,
        causal_id=causal_id,
        payload=payload_dict,
    )
