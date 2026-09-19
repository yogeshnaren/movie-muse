"""Candidates never auto-promote; rejected ideas stay out of active context."""

from __future__ import annotations

import pytest

from movie_muse.identity.api import make_integration_actor
from movie_muse.project_memory.api import (
    AutoPromoteError,
    CandidateClosedError,
    DuplicateCandidateError,
    HumanRequiredError,
    MemoryCandidateKind,
    MemoryStatus,
    ProjectMemoryKind,
    UnpromotableKindError,
)
from movie_muse.schemas.api import new_id


def test_capture_does_not_create_canon_and_refuses_auto_promote(memory_stack) -> None:
    with pytest.raises(AutoPromoteError):
        memory_stack.memory.capture(
            project_id=memory_stack.project.id,
            kind=MemoryCandidateKind.FACT,
            summary="Ada has the brass key",
            principal=memory_stack.principal,
            acl_epoch=memory_stack.epoch,
            branch_id=memory_stack.branch_id,
            revision_id=memory_stack.document.base_revision_id,
            auto_promote=True,
        )
    candidate = memory_stack.memory.capture(
        project_id=memory_stack.project.id,
        kind=MemoryCandidateKind.FACT,
        summary="Ada has the brass key",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
        branch_id=memory_stack.branch_id,
        revision_id=memory_stack.document.base_revision_id,
    )
    assert candidate.status is MemoryStatus.CAPTURED
    assert memory_stack.memory.list_memories(
        memory_stack.project.id,
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
    ) == ()


def test_human_promote_creates_project_memory_with_provenance(memory_stack) -> None:
    event_id = new_id("collaboration_event")
    candidate = memory_stack.memory.capture(
        project_id=memory_stack.project.id,
        kind=MemoryCandidateKind.DECISION,
        summary="Keep the kitchen lock brass",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
        branch_id=memory_stack.branch_id,
        revision_id=memory_stack.document.base_revision_id,
        source_collaboration_event_id=event_id,
    )
    memory = memory_stack.memory.promote(
        candidate.id,
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
    )
    assert memory.kind is ProjectMemoryKind.DECISION
    assert memory.reviewed_by_actor_id == memory_stack.owner.id
    assert memory.source_collaboration_event_id == event_id
    assert memory.id.startswith("mem_")
    active = memory_stack.memory.list_memories(
        memory_stack.project.id,
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
    )
    assert [item.id for item in active] == [memory.id]
    closed = memory_stack.memory.get_candidate(candidate.id)
    assert closed.status is MemoryStatus.PROMOTED
    assert closed.promoted_memory_id == memory.id
    assert any(entry.operation == "promote" for entry in closed.provenance)
    operations = [record.operation for record in memory_stack.audit.list_records()]
    assert "project_memory.promote" in operations


def test_rejected_ideas_are_retrievable_but_not_active(memory_stack) -> None:
    captured = memory_stack.memory.capture(
        project_id=memory_stack.project.id,
        kind=MemoryCandidateKind.IDEA,
        summary="Ada jumps the harbor crane",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
        branch_id=memory_stack.branch_id,
        revision_id=memory_stack.document.base_revision_id,
    )
    rejected = memory_stack.memory.reject(
        captured.id,
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
        note="too expensive",
    )
    assert rejected.status is MemoryStatus.REJECTED
    active = memory_stack.memory.search(
        project_id=memory_stack.project.id,
        query="harbor crane",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
    )
    assert active == ()
    recovered = memory_stack.memory.search(
        project_id=memory_stack.project.id,
        query="harbor crane",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
        include_rejected=True,
    )
    assert recovered[0].id == captured.id
    assert memory_stack.memory.list_memories(
        memory_stack.project.id,
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
    ) == ()
    immediate = memory_stack.memory.capture(
        project_id=memory_stack.project.id,
        kind=MemoryCandidateKind.REJECTED_IDEA,
        summary="Cut the kitchen scene",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
        branch_id=memory_stack.branch_id,
        revision_id=memory_stack.document.base_revision_id,
    )
    assert immediate.status is MemoryStatus.REJECTED


def test_edit_preserves_capture_provenance(memory_stack) -> None:
    candidate = memory_stack.memory.capture(
        project_id=memory_stack.project.id,
        kind=MemoryCandidateKind.QUESTION,
        summary="Does Ben know the lock is open?",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
        branch_id=memory_stack.branch_id,
        revision_id=memory_stack.document.base_revision_id,
    )
    edited = memory_stack.memory.edit(
        candidate.id,
        summary="Does Ben believe the lock is open?",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
    )
    assert edited.id == candidate.id
    assert edited.captured_at == candidate.captured_at
    assert edited.captured_by_actor_id == candidate.captured_by_actor_id
    assert [entry.operation for entry in edited.provenance] == ["capture", "edit"]
    assert edited.summary.startswith("Does Ben believe")


def test_duplicate_conflict_and_supersede(memory_stack) -> None:
    first = memory_stack.memory.capture(
        project_id=memory_stack.project.id,
        kind=MemoryCandidateKind.ASSIGNMENT,
        summary="Prop master confirms the key",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
        branch_id=memory_stack.branch_id,
        revision_id=memory_stack.document.base_revision_id,
    )
    with pytest.raises(DuplicateCandidateError):
        memory_stack.memory.capture(
            project_id=memory_stack.project.id,
            kind=MemoryCandidateKind.ASSIGNMENT,
            summary="Prop master confirms the key",
            principal=memory_stack.principal,
            acl_epoch=memory_stack.epoch,
            branch_id=memory_stack.branch_id,
            revision_id=memory_stack.document.base_revision_id,
        )
    second = memory_stack.memory.capture(
        project_id=memory_stack.project.id,
        kind=MemoryCandidateKind.ASSIGNMENT,
        summary="Prop master confirms the key",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
        branch_id=memory_stack.branch_id,
        revision_id=memory_stack.document.base_revision_id,
        supersede_id=first.id,
    )
    assert memory_stack.memory.get_candidate(first.id).status is MemoryStatus.REJECTED
    assert second.conflict_of_id == first.id


def test_idea_and_link_cannot_become_schema_memory(memory_stack) -> None:
    idea = memory_stack.memory.capture(
        project_id=memory_stack.project.id,
        kind=MemoryCandidateKind.IDEA,
        summary="Open on the tide instead",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
        branch_id=memory_stack.branch_id,
        revision_id=memory_stack.document.base_revision_id,
    )
    with pytest.raises(UnpromotableKindError):
        memory_stack.memory.promote(
            idea.id, principal=memory_stack.principal, acl_epoch=memory_stack.epoch
        )
    link = memory_stack.memory.capture(
        project_id=memory_stack.project.id,
        kind=MemoryCandidateKind.LINK,
        summary="Harbor tide table",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
        branch_id=memory_stack.branch_id,
        revision_id=memory_stack.document.base_revision_id,
        link_url="https://example.invalid/tide",
        artifact_id="art_placeholder",
    )
    assert link.link_url.endswith("/tide")
    with pytest.raises(UnpromotableKindError):
        memory_stack.memory.promote(
            link.id, principal=memory_stack.principal, acl_epoch=memory_stack.epoch
        )


def test_integration_cannot_promote_or_reject(memory_stack) -> None:
    candidate = memory_stack.memory.capture(
        project_id=memory_stack.project.id,
        kind=MemoryCandidateKind.RESEARCH,
        summary="Humidity sticks the pantry lock",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
        branch_id=memory_stack.branch_id,
        revision_id=memory_stack.document.base_revision_id,
    )
    bot = make_integration_actor(
        organization_id=memory_stack.project.organization_id, display_name="Harvester"
    )
    memory_stack.identity.register_actor(bot)
    bot_principal = memory_stack.identity.principal(bot.id)
    with pytest.raises(HumanRequiredError):
        memory_stack.memory.promote(
            candidate.id, principal=bot_principal, acl_epoch=memory_stack.epoch
        )
    with pytest.raises(HumanRequiredError):
        memory_stack.memory.reject(
            candidate.id, principal=bot_principal, acl_epoch=memory_stack.epoch
        )
    memory_stack.memory.promote(
        candidate.id, principal=memory_stack.principal, acl_epoch=memory_stack.epoch
    )
    with pytest.raises(CandidateClosedError):
        memory_stack.memory.promote(
            candidate.id, principal=memory_stack.principal, acl_epoch=memory_stack.epoch
        )


def test_search_is_branch_scoped(memory_stack) -> None:
    memory_stack.memory.capture(
        project_id=memory_stack.project.id,
        kind=MemoryCandidateKind.FACT,
        summary="Ada keeps the brass key",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
        branch_id=memory_stack.branch_id,
        revision_id=memory_stack.document.base_revision_id,
    )
    other_branch = new_id("branch")
    memory_stack.memory.capture(
        project_id=memory_stack.project.id,
        kind=MemoryCandidateKind.FACT,
        summary="Ada keeps the brass key on the other branch",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
        branch_id=other_branch,
        revision_id=memory_stack.document.base_revision_id,
    )
    hits = memory_stack.memory.search(
        project_id=memory_stack.project.id,
        query="brass key",
        principal=memory_stack.principal,
        acl_epoch=memory_stack.epoch,
        branch_id=memory_stack.branch_id,
    )
    assert len(hits) == 1
    assert hits[0].branch_id == memory_stack.branch_id
