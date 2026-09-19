"""Least scopes, signed callbacks, replay protection, expired/revoked tokens."""

from __future__ import annotations

import json
import os

import pytest

from movie_muse.adapters.zoom.api import (
    LEAST_SCOPES,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    ZOOM_SANDBOX_ENV,
    ZoomSandboxUnavailableError,
    ZoomScopeError,
    ZoomTokenError,
    ZoomWebhookError,
    require_zoom_sandbox,
    sign_zoom_payload,
    zoom_authorization_url,
)
from movie_muse.meeting_capture.api import CaptureState, ConsentRequiredError, ConsentState

SIGNING_KEY = "zoom-contract-hmac"


def _credential(stack, *, expires_at: str = "2026-12-01T00:00:00Z"):
    return stack.zoom.register_credential(
        project_id=stack.project.id,
        scopes=LEAST_SCOPES,
        expires_at=expires_at,
        token_digest="digest_local_not_a_live_token",
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )


def _consented_meeting(stack):
    view = stack.zoom.prepare_import(
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


def _webhook(stack, meeting_id: str, event_id: str = "evt_zoom_1"):
    body = json.dumps(
        {
            "event_id": event_id,
            "meeting_id": meeting_id,
            "utterances": [
                {
                    "speaker_label": "Ada",
                    "start_ms": 0,
                    "end_ms": 1200,
                    "text": "Keep the child back.",
                }
            ],
        }
    ).encode("utf-8")
    timestamp = stack.clock.unix()
    headers = {
        TIMESTAMP_HEADER: timestamp,
        SIGNATURE_HEADER: sign_zoom_payload(SIGNING_KEY, timestamp, body),
    }
    return headers, body


def test_authorization_url_declares_least_scopes() -> None:
    url = zoom_authorization_url(
        client_id="zoom_client",
        redirect_uri="https://moviemuse.example/oauth/zoom",
        state="state-1",
    )
    assert "response_type=code" in url
    assert "meeting%3Aread" in url or "meeting:read" in url
    assert "recording%3Aread" in url or "recording:read" in url
    assert "user:write" not in url


def test_extra_scopes_are_rejected(zoom_stack) -> None:
    with pytest.raises(ZoomScopeError):
        zoom_stack.zoom.register_credential(
            project_id=zoom_stack.project.id,
            scopes=LEAST_SCOPES + ("user:write",),
            expires_at="2026-12-01T00:00:00Z",
            token_digest="x",
            principal=zoom_stack.principal,
            acl_epoch=zoom_stack.epoch,
        )


def test_consent_required_before_webhook_import(zoom_stack) -> None:
    credential = _credential(zoom_stack)
    view = zoom_stack.zoom.prepare_import(
        project_id=zoom_stack.project.id,
        branch_id=zoom_stack.branch_id,
        revision_id=zoom_stack.revisions.canon_head_id(),
        principal=zoom_stack.principal,
        acl_epoch=zoom_stack.epoch,
    )
    assert view.visible is True
    assert view.consent_state is ConsentState.PENDING
    headers, body = _webhook(zoom_stack, view.meeting_id)
    with pytest.raises(ZoomWebhookError):
        zoom_stack.zoom.handle_webhook(
            headers=headers,
            body=body,
            credential_id=credential.id,
            principal=zoom_stack.principal,
            acl_epoch=zoom_stack.epoch,
        )
    with pytest.raises(ConsentRequiredError):
        zoom_stack.meetings.start_recording(
            view.meeting_id,
            principal=zoom_stack.principal,
            acl_epoch=zoom_stack.epoch,
        )


def test_signed_webhook_imports_after_consent(zoom_stack) -> None:
    credential = _credential(zoom_stack)
    meeting_id = _consented_meeting(zoom_stack)
    headers, body = _webhook(zoom_stack, meeting_id)
    imported = zoom_stack.zoom.handle_webhook(
        headers=headers,
        body=body,
        credential_id=credential.id,
        principal=zoom_stack.principal,
        acl_epoch=zoom_stack.epoch,
    )
    assert imported.capture_state is CaptureState.IMPORTED
    assert imported.utterances[0].text == "Keep the child back."
    with pytest.raises(ZoomWebhookError):
        zoom_stack.zoom.handle_webhook(
            headers=headers,
            body=body,
            credential_id=credential.id,
            principal=zoom_stack.principal,
            acl_epoch=zoom_stack.epoch,
        )


def test_invalid_signature_is_rejected(zoom_stack) -> None:
    credential = _credential(zoom_stack)
    meeting_id = _consented_meeting(zoom_stack)
    headers, body = _webhook(zoom_stack, meeting_id)
    headers[SIGNATURE_HEADER] = "v0=deadbeef"
    with pytest.raises(ZoomWebhookError):
        zoom_stack.zoom.handle_webhook(
            headers=headers,
            body=body,
            credential_id=credential.id,
            principal=zoom_stack.principal,
            acl_epoch=zoom_stack.epoch,
        )


def test_expired_and_revoked_tokens_fail_closed(zoom_stack) -> None:
    expired = _credential(zoom_stack, expires_at="2026-01-01T00:00:00Z")
    meeting_id = _consented_meeting(zoom_stack)
    headers, body = _webhook(zoom_stack, meeting_id, event_id="evt_expired")
    with pytest.raises(ZoomTokenError):
        zoom_stack.zoom.handle_webhook(
            headers=headers,
            body=body,
            credential_id=expired.id,
            principal=zoom_stack.principal,
            acl_epoch=zoom_stack.epoch,
        )
    active = _credential(zoom_stack)
    zoom_stack.zoom.revoke_credential(
        active.id, principal=zoom_stack.principal, acl_epoch=zoom_stack.epoch
    )
    headers, body = _webhook(zoom_stack, meeting_id, event_id="evt_revoked")
    with pytest.raises(ZoomTokenError):
        zoom_stack.zoom.handle_webhook(
            headers=headers,
            body=body,
            credential_id=active.id,
            principal=zoom_stack.principal,
            acl_epoch=zoom_stack.epoch,
        )


def test_live_sandbox_unset_fails_closed(zoom_stack) -> None:
    os.environ.pop(ZOOM_SANDBOX_ENV, None)
    with pytest.raises(ZoomSandboxUnavailableError):
        require_zoom_sandbox()
    credential = _credential(zoom_stack)
    with pytest.raises(ZoomSandboxUnavailableError):
        zoom_stack.zoom.exchange_authorization_code(
            "code-from-zoom",
            principal=zoom_stack.principal,
            acl_epoch=zoom_stack.epoch,
            project_id=zoom_stack.project.id,
        )
    with pytest.raises(ZoomSandboxUnavailableError):
        zoom_stack.zoom.import_live_recording(
            credential.id,
            principal=zoom_stack.principal,
            acl_epoch=zoom_stack.epoch,
        )
