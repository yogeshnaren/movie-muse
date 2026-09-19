"""Unlock/repagination events using the closed ProductionRequirementConfirmed type."""

from __future__ import annotations

from movie_muse.schemas.api import (
    ProjectEvent,
    compute_integrity_hash,
    new_id,
    new_ulid,
)

EVENT_TYPE = "ProductionRequirementConfirmed"


def make_unlock_event(
    *,
    project_id: str,
    branch_id: str,
    result_revision_id: str,
    actor_id: str,
    created_at: str = "2026-09-01T00:00:00Z",
    base_revision_id: str | None = None,
) -> ProjectEvent:
    command = new_ulid()
    operation = new_ulid()
    payload = {
        "requirement": "unlock_repagination",
        "engine": "layout",
    }
    integrity = compute_integrity_hash(
        project_id=project_id,
        branch_id=branch_id,
        base_revision_id=base_revision_id,
        result_revision_id=result_revision_id,
        actor_id=actor_id,
        effective_principal_id=actor_id,
        command_id=command,
        operation_id=operation,
        event_type=EVENT_TYPE,
        schema_version="1.0",
        causal_id=None,
        correlation_id=command,
        payload=payload,
    )
    return ProjectEvent(
        id=new_id("event"),
        project_id=project_id,
        branch_id=branch_id,
        result_revision_id=result_revision_id,
        actor_id=actor_id,
        effective_principal_id=actor_id,
        command_id=command,
        operation_id=operation,
        event_type=EVENT_TYPE,
        created_at=created_at,
        correlation_id=command,
        integrity_hash=integrity,
        base_revision_id=base_revision_id,
        payload=payload,
    )
