"""Room Harvest requires explicit review and never auto-promotes."""

from __future__ import annotations

import pytest

from movie_muse.project_memory.api import MemoryCandidateKind, MemoryStatus, ProjectMemoryKind
from movie_muse.room_mode.api import (
    HarvestItemState,
    HarvestNotOpenError,
    HarvestRequiresReviewError,
)


def _open(room_stack):
    return room_stack.rooms.start_room(
        project_id=room_stack.project.id,
        branch_id=room_stack.branch_id,
        revision_id=room_stack.document.base_revision_id,
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
    )


def test_capture_refuses_auto_promote(room_stack) -> None:
    session = _open(room_stack)
    with pytest.raises(HarvestRequiresReviewError):
        room_stack.rooms.capture(
            session.id,
            summary="Ada has the brass key",
            principal=room_stack.principal,
            acl_epoch=room_stack.epoch,
            kind=MemoryCandidateKind.DECISION,
            auto_promote=True,
        )
    candidate = room_stack.rooms.capture(
        session.id,
        summary="Ada has the brass key",
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
        kind=MemoryCandidateKind.DECISION,
    )
    assert candidate.status is MemoryStatus.CAPTURED
    assert room_stack.memory.list_memories(
        room_stack.project.id,
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
    ) == ()


def test_harvest_promote_requires_review_then_creates_memory(room_stack) -> None:
    session = _open(room_stack)
    candidate = room_stack.rooms.capture(
        session.id,
        summary="Keep the kitchen lock brass",
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
        kind=MemoryCandidateKind.DECISION,
    )
    with pytest.raises(HarvestNotOpenError):
        room_stack.rooms.harvest_promote(
            session.id,
            candidate.id,
            principal=room_stack.principal,
            acl_epoch=room_stack.epoch,
        )
    items = room_stack.rooms.start_harvest_review(
        session.id,
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
    )
    assert items[0].state is HarvestItemState.UNDER_REVIEW
    memory = room_stack.rooms.harvest_promote(
        session.id,
        candidate.id,
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
    )
    assert memory.kind is ProjectMemoryKind.DECISION
    assert memory.source_collaboration_event_id is not None
    closed = room_stack.memory.get_candidate(candidate.id)
    assert closed.status is MemoryStatus.PROMOTED
    assert closed.promoted_memory_id == memory.id
    harvest = room_stack.rooms.list_harvest(session.id)
    assert harvest[0].state is HarvestItemState.PROMOTED


def test_harvest_discard_keeps_rejected_out_of_active_memory(room_stack) -> None:
    session = _open(room_stack)
    candidate = room_stack.rooms.capture(
        session.id,
        summary="Cut the harbor night",
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
        kind=MemoryCandidateKind.IDEA,
    )
    room_stack.rooms.start_harvest_review(
        session.id,
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
    )
    rejected = room_stack.rooms.harvest_discard(
        session.id,
        candidate.id,
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
        note="keep the night",
    )
    assert rejected.status is MemoryStatus.REJECTED
    assert room_stack.memory.list_memories(
        room_stack.project.id,
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
    ) == ()
    found = room_stack.memory.search(
        project_id=room_stack.project.id,
        query="harbor",
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
        include_rejected=True,
    )
    assert found[0].id == candidate.id
