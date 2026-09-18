"""Consent is visible; recording/import fail closed without it."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import Role, make_human_actor
from movie_muse.meeting_capture.api import (
    CaptureState,
    ConsentDeniedError,
    ConsentRequiredError,
    ConsentState,
    MeetingDeletedError,
    RetentionExpiredError,
    Utterance,
)
from movie_muse.schemas.api import new_ulid


def _open(meeting_stack, *, retention_days: int = 30):
    return meeting_stack.meetings.begin_session(
        project_id=meeting_stack.project.id,
        branch_id=meeting_stack.branch_id,
        revision_id=meeting_stack.revisions.canon_head_id(),
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
        retention_days=retention_days,
    )


def test_consent_state_is_visible_and_blocks_capture(meeting_stack) -> None:
    session = _open(meeting_stack)
    view = meeting_stack.meetings.consent_view(session.id)
    assert view.visible is True
    assert view.consent_state is ConsentState.PENDING
    assert view.capture_state is CaptureState.CONSENT_REQUIRED
    with pytest.raises(ConsentRequiredError):
        meeting_stack.meetings.start_recording(
            session.id,
            principal=meeting_stack.principal,
            acl_epoch=meeting_stack.epoch,
        )
    granted = meeting_stack.meetings.grant_consent(
        session.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    assert granted.consent_state is ConsentState.GRANTED
    shown = meeting_stack.meetings.consent_view(session.id)
    assert shown.consent_state is ConsentState.GRANTED
    assert shown.actor_id == meeting_stack.owner.id
    recording = meeting_stack.meetings.start_recording(
        session.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    assert recording.capture_state is CaptureState.RECORDING


def test_denied_and_withdrawn_consent_fail_closed(meeting_stack) -> None:
    denied = _open(meeting_stack)
    meeting_stack.meetings.deny_consent(
        denied.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    with pytest.raises(ConsentDeniedError):
        meeting_stack.meetings.import_transcript(
            denied.id,
            utterances=(),
            principal=meeting_stack.principal,
            acl_epoch=meeting_stack.epoch,
        )
    withdrawn = _open(meeting_stack)
    meeting_stack.meetings.grant_consent(
        withdrawn.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    meeting_stack.meetings.start_recording(
        withdrawn.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    meeting_stack.meetings.withdraw_consent(
        withdrawn.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    assert meeting_stack.meetings.consent_view(withdrawn.id).consent_state is ConsentState.WITHDRAWN
    with pytest.raises(ConsentDeniedError):
        meeting_stack.meetings.start_recording(
            withdrawn.id,
            principal=meeting_stack.principal,
            acl_epoch=meeting_stack.epoch,
        )


def test_viewer_cannot_import_transcript(meeting_stack) -> None:
    session = _open(meeting_stack)
    meeting_stack.meetings.grant_consent(
        session.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    actor = make_human_actor(
        organization_id=meeting_stack.project.organization_id, display_name="Viewer"
    )
    meeting_stack.identity.register_actor(actor)
    invitation = meeting_stack.identity.invite(
        inviter_actor_id=meeting_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=meeting_stack.project.id,
        role=Role.VIEWER,
    )
    meeting_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    viewer = meeting_stack.identity.principal(actor.id)
    with pytest.raises(AuthorizationError):
        meeting_stack.meetings.import_transcript(
            session.id,
            utterances=(
                Utterance(
                    id=f"utt_{new_ulid()}",
                    speaker_label="Ada",
                    start_ms=0,
                    end_ms=1000,
                    text="Keep the brass key.",
                ),
            ),
            principal=viewer,
            acl_epoch=meeting_stack.identity.acl_epoch(),
        )


def test_delete_and_retention_expire(meeting_stack) -> None:
    session = _open(meeting_stack, retention_days=1)
    meeting_stack.meetings.grant_consent(
        session.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    meeting_stack.meetings.import_transcript(
        session.id,
        utterances=(
            Utterance(
                id=f"utt_{new_ulid()}",
                speaker_label="Ada",
                start_ms=0,
                end_ms=1500,
                text="Harbor night stays.",
            ),
        ),
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    deleted = meeting_stack.meetings.delete_session(
        session.id,
        principal=meeting_stack.principal,
        acl_epoch=meeting_stack.epoch,
    )
    assert deleted.capture_state is CaptureState.DELETED
    assert deleted.utterances == ()
    with pytest.raises(MeetingDeletedError):
        meeting_stack.meetings.get_session(
            session.id,
            principal=meeting_stack.principal,
            acl_epoch=meeting_stack.epoch,
        )
    retained = _open(meeting_stack, retention_days=1)
    meeting_stack.clock.advance(86_400 + 1)
    with pytest.raises(RetentionExpiredError):
        meeting_stack.meetings.get_session(
            retained.id,
            principal=meeting_stack.principal,
            acl_epoch=meeting_stack.epoch,
        )
