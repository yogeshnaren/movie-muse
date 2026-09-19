"""Transcript edits keep provenance; harvest never auto-promotes."""

from __future__ import annotations

import pytest

from movie_muse.meeting_capture.api import (
    HarvestItemState,
    HarvestNotOpenError,
    HarvestRequiresReviewError,
    MediaLink,
    Utterance,
)
from movie_muse.project_memory.api import MemoryCandidateKind, MemoryStatus, ProjectMemoryKind
from movie_muse.schemas.api import new_ulid


def _imported(meeting_stack):
    session = meeting_stack.meetings.begin_session(
        project_id=meeting_stack.project.id,
        branch_id=meeting_stack.branch_id,
        revision_id=meeting_stack.revisions.canon_head_id(),
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    meeting_stack.meetings.grant_consent(
        session.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    utterance = Utterance(
        id=f"utt_{new_ulid()}",
        speaker_label="Speaker 1",
        start_ms=0,
        end_ms=2400,
        text="Keep the kitchen lock brass.",
    )
    imported = meeting_stack.meetings.import_transcript(
        session.id,
        utterances=(utterance,),
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
        media_links=(
            MediaLink(
                id=f"mlk_{new_ulid()}",
                title="Harbor night clip",
                uri="mm://media/harbor",
                start_ms=0,
                utterance_id=utterance.id,
            ),
        ),
    )
    return imported, utterance.id


def test_speaker_and_text_edits_keep_provenance(meeting_stack) -> None:
    session, utterance_id = _imported(meeting_stack)
    first_version = session.artifact_version_id
    corrected = meeting_stack.meetings.correct_speaker(
        session.id,
        utterance_id,
        speaker_label="Ada",
        speaker_actor_id=meeting_stack.owner.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    assert corrected.speaker_label == "Ada"
    assert corrected.speaker_actor_id == meeting_stack.owner.id
    assert any(entry.operation == "import" for entry in corrected.provenance)
    assert any(entry.operation == "correct_speaker" for entry in corrected.provenance)
    assert "Speaker 1->Ada" in corrected.provenance[-1].note
    edited = meeting_stack.meetings.edit_utterance(
        session.id,
        utterance_id,
        text="Keep the brass kitchen lock.",
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    assert edited.text == "Keep the brass kitchen lock."
    assert any(entry.operation == "edit_text" for entry in edited.provenance)
    current = meeting_stack.meetings.get_session(
        session.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    assert current.artifact_version_id != first_version
    assert current.utterances[0].id == utterance_id


def test_media_links_and_utterances_are_searchable(meeting_stack) -> None:
    session, _utterance_id = _imported(meeting_stack)
    hits = meeting_stack.meetings.search(
        session.id,
        "harbor",
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    assert any(getattr(item, "title", "") == "Harbor night clip" for item in hits)
    text_hits = meeting_stack.meetings.search(
        session.id,
        "kitchen lock",
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    assert any(getattr(item, "text", "").startswith("Keep the kitchen") for item in text_hits)


def test_extract_refuses_auto_promote_and_harvest_requires_review(meeting_stack) -> None:
    session, utterance_id = _imported(meeting_stack)
    with pytest.raises(HarvestRequiresReviewError):
        meeting_stack.meetings.extract_candidate(
            session.id,
            summary="Keep the kitchen lock brass",
            principal=meeting_stack.principal,
            acl_epoch=meeting_stack.epoch,
            kind=MemoryCandidateKind.DECISION,
            utterance_id=utterance_id,
            auto_promote=True,
        )
    candidate = meeting_stack.meetings.extract_candidate(
        session.id,
        summary="Keep the kitchen lock brass",
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
        kind=MemoryCandidateKind.DECISION,
        utterance_id=utterance_id,
    )
    assert candidate.status is MemoryStatus.CAPTURED
    assert candidate.artifact_id == session.artifact_id
    assert meeting_stack.memory.list_memories(
        meeting_stack.project.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    ) == ()
    with pytest.raises(HarvestNotOpenError):
        meeting_stack.meetings.harvest_promote(
            session.id,
            candidate.id,
            principal=meeting_stack.principal,
            acl_epoch=meeting_stack.epoch,
        )
    items = meeting_stack.meetings.start_harvest_review(
        session.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    assert items[0].state is HarvestItemState.UNDER_REVIEW
    memory = meeting_stack.meetings.harvest_promote(
        session.id,
        candidate.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    assert memory.kind is ProjectMemoryKind.DECISION
    closed = meeting_stack.memory.get_candidate(candidate.id)
    assert closed.status is MemoryStatus.PROMOTED


def test_harvest_discard_stays_out_of_active_memory(meeting_stack) -> None:
    session, utterance_id = _imported(meeting_stack)
    candidate = meeting_stack.meetings.extract_candidate(
        session.id,
        summary="Cut the harbor night",
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
        kind=MemoryCandidateKind.IDEA,
        utterance_id=utterance_id,
    )
    meeting_stack.meetings.start_harvest_review(
        session.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    rejected = meeting_stack.meetings.harvest_discard(
        session.id,
        candidate.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
        note="keep the night",
    )
    assert rejected.status is MemoryStatus.REJECTED
    assert meeting_stack.memory.list_memories(
        meeting_stack.project.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    ) == ()
