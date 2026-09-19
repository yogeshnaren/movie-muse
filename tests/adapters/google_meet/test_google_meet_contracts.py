"""Least scopes, signed callbacks, replay protection, expired/revoked tokens."""

from __future__ import annotations

import json
import os

import pytest

from movie_muse.adapters.google_meet.api import (
    GOOGLE_MEET_SANDBOX_ENV,
    LEAST_SCOPES,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    GoogleMeetSandboxUnavailableError,
    GoogleMeetScopeError,
    GoogleMeetTokenError,
    GoogleMeetWebhookError,
    google_meet_authorization_url,
    require_google_meet_sandbox,
    sign_google_meet_payload,
)
from movie_muse.meeting_capture.api import CaptureState, ConsentState

SIGNING_KEY = "meet-contract-hmac"


def _credential(stack, *, expires_at: str = "2026-12-01T00:00:00Z"):
    return stack.meet.register_credential(
        project_id=stack.project.id,
        scopes=LEAST_SCOPES,
        expires_at=expires_at,
        token_digest="digest_local_not_a_live_token",
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )


def _consented_meeting(stack):
    view = stack.meet.prepare_import(
        project_id=stack.project.id,
        branch_id=stack.branch_id,
        revision_id=stack.revisions.canon_head_id(),
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    stack.meetings.grant_consent(
        view.meeting_id, principal=stack.principal, acl_epoch=stack.epoch
    )
    return view.meeting_id


def _webhook(stack, meeting_id: str, event_id: str = "evt_meet_1"):
    body = json.dumps(
        {
            "event_id": event_id,
            "meeting_id": meeting_id,
            "utterances": [
                {
                    "speaker_label": "Ada",
                    "start_ms": 0,
                    "end_ms": 900,
                    "text": "Share the call sheet.",
                }
            ],
        }
    ).encode("utf-8")
    timestamp = stack.clock.unix()
    headers = {
        TIMESTAMP_HEADER: timestamp,
        SIGNATURE_HEADER: sign_google_meet_payload(SIGNING_KEY, timestamp, body),
    }
    return headers, body


def test_authorization_url_declares_least_scopes() -> None:
    url = google_meet_authorization_url(
        client_id="meet_client",
        redirect_uri="https://moviemuse.example/oauth/meet",
        state="state-1",
    )
    assert "response_type=code" in url
    assert "meetings.space.readonly" in url


def test_extra_scopes_are_rejected(meet_stack) -> None:
    with pytest.raises(GoogleMeetScopeError):
        meet_stack.meet.register_credential(
            project_id=meet_stack.project.id,
            scopes=LEAST_SCOPES + ("https://www.googleapis.com/auth/drive",),
            expires_at="2026-12-01T00:00:00Z",
            token_digest="x",
            principal=meet_stack.principal,
            acl_epoch=meet_stack.epoch,
        )


def test_consent_required_before_webhook_import(meet_stack) -> None:
    credential = _credential(meet_stack)
    view = meet_stack.meet.prepare_import(
        project_id=meet_stack.project.id,
        branch_id=meet_stack.branch_id,
        revision_id=meet_stack.revisions.canon_head_id(),
        principal=meet_stack.principal,
        acl_epoch=meet_stack.epoch,
    )
    assert view.consent_state is ConsentState.PENDING
    headers, body = _webhook(meet_stack, view.meeting_id)
    with pytest.raises(GoogleMeetWebhookError):
        meet_stack.meet.handle_webhook(
            headers=headers,
            body=body,
            credential_id=credential.id,
            principal=meet_stack.principal,
            acl_epoch=meet_stack.epoch,
        )


def test_signed_webhook_imports_after_consent_and_rejects_replay(meet_stack) -> None:
    credential = _credential(meet_stack)
    meeting_id = _consented_meeting(meet_stack)
    headers, body = _webhook(meet_stack, meeting_id)
    imported = meet_stack.meet.handle_webhook(
        headers=headers,
        body=body,
        credential_id=credential.id,
        principal=meet_stack.principal,
        acl_epoch=meet_stack.epoch,
    )
    assert imported.capture_state is CaptureState.IMPORTED
    assert imported.utterances[0].text == "Share the call sheet."
    with pytest.raises(GoogleMeetWebhookError):
        meet_stack.meet.handle_webhook(
            headers=headers,
            body=body,
            credential_id=credential.id,
            principal=meet_stack.principal,
            acl_epoch=meet_stack.epoch,
        )


def test_expired_and_revoked_tokens_fail_closed(meet_stack) -> None:
    expired = _credential(meet_stack, expires_at="2026-01-01T00:00:00Z")
    meeting_id = _consented_meeting(meet_stack)
    headers, body = _webhook(meet_stack, meeting_id, event_id="evt_expired")
    with pytest.raises(GoogleMeetTokenError):
        meet_stack.meet.handle_webhook(
            headers=headers,
            body=body,
            credential_id=expired.id,
            principal=meet_stack.principal,
            acl_epoch=meet_stack.epoch,
        )
    active = _credential(meet_stack)
    meet_stack.meet.revoke_credential(
        active.id, principal=meet_stack.principal, acl_epoch=meet_stack.epoch
    )
    headers, body = _webhook(meet_stack, meeting_id, event_id="evt_revoked")
    with pytest.raises(GoogleMeetTokenError):
        meet_stack.meet.handle_webhook(
            headers=headers,
            body=body,
            credential_id=active.id,
            principal=meet_stack.principal,
            acl_epoch=meet_stack.epoch,
        )


def test_live_sandbox_unset_fails_closed(meet_stack) -> None:
    os.environ.pop(GOOGLE_MEET_SANDBOX_ENV, None)
    with pytest.raises(GoogleMeetSandboxUnavailableError):
        require_google_meet_sandbox()
    credential = _credential(meet_stack)
    with pytest.raises(GoogleMeetSandboxUnavailableError):
        meet_stack.meet.exchange_authorization_code(
            "code-from-meet",
            principal=meet_stack.principal,
            acl_epoch=meet_stack.epoch,
            project_id=meet_stack.project.id,
        )
    with pytest.raises(GoogleMeetSandboxUnavailableError):
        meet_stack.meet.import_live_recording(
            credential.id,
            principal=meet_stack.principal,
            acl_epoch=meet_stack.epoch,
        )
