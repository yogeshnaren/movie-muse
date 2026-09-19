"""Replaceable Zoom OAuth/webhook/import adapter with fail-closed live sandbox."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from movie_muse.adapters.zoom.errors import (
    ZoomSandboxUnavailableError,
    ZoomScopeError,
    ZoomTokenError,
    ZoomWebhookError,
)
from movie_muse.adapters.zoom.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.adapters.zoom.types import (
    LEAST_SCOPES,
    REPLAY_WINDOW_SECONDS,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    ZOOM_AUTHORIZE_URL,
    ZOOM_SANDBOX_ENV,
    CredentialStatus,
    ZoomCredential,
)
from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.identity.api import Principal
from movie_muse.meeting_capture.api import (
    ConsentState,
    ConsentView,
    MeetingCaptureService,
    MeetingSession,
    Utterance,
)
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.schemas.api import new_ulid


def zoom_sandbox_base_url() -> str | None:
    value = os.environ.get(ZOOM_SANDBOX_ENV, "").strip()
    return value or None


def require_zoom_sandbox() -> str:
    base = zoom_sandbox_base_url()
    if not base:
        raise ZoomSandboxUnavailableError(
            f"{ZOOM_SANDBOX_ENV} is unset; EXT-ZOOM-SANDBOX stays NOT_RUN "
            "(fail-closed, not skipped; mocks do not satisfy the live gate)"
        )
    return base


def sign_zoom_payload(secret: str, timestamp: str, body: bytes) -> str:
    mac = hmac.new(
        secret.encode(),
        f"{timestamp}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()
    return f"v0={mac}"


def zoom_authorization_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(LEAST_SCOPES),
            "state": state,
        }
    )
    return f"{ZOOM_AUTHORIZE_URL}?{query}"


class ZoomAdapter:
    """Least-scope Zoom adapter. Consent-first import. Live sandbox is not mocked."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        meetings: MeetingCaptureService,
        authorization: AuthorizationService,
        audit: AuditLog,
        *,
        webhook_secret: str,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.meetings = meetings
        self.authorization = authorization
        self.audit = audit
        self.webhook_secret = webhook_secret
        self.clock = clock

    def exchange_authorization_code(
        self,
        code: str,
        *,
        principal: Principal,
        acl_epoch: int,
        project_id: str,
    ) -> ZoomCredential:
        del code
        self._require(principal, Action.RUN_PAID_PROVIDER, project_id, acl_epoch)
        require_zoom_sandbox()
        raise ZoomSandboxUnavailableError(
            "Zoom OAuth token exchange is not completed without a live sandbox; "
            "EXT-ZOOM-SANDBOX stays NOT_RUN"
        )

    def register_credential(
        self,
        *,
        project_id: str,
        scopes: tuple[str, ...],
        expires_at: str,
        token_digest: str,
        principal: Principal,
        acl_epoch: int,
    ) -> ZoomCredential:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        requested = tuple(sorted(set(scopes)))
        if requested != tuple(sorted(LEAST_SCOPES)):
            raise ZoomScopeError(
                f"Zoom adapter stores only least scopes {LEAST_SCOPES}; got {requested}"
            )
        credential = ZoomCredential(
            id=f"tok_{new_ulid()}",
            project_id=project_id,
            actor_id=principal.actor_id,
            scopes=requested,
            status=CredentialStatus.ACTIVE,
            expires_at=expires_at,
            token_digest=token_digest,
            created_at=self.clock(),
        )
        written = self._put_credential(credential)
        self._audit(principal, acl_epoch, "zoom.credential_register", written.id, "least_scopes")
        return written

    def expire_credential(
        self, credential_id: str, *, principal: Principal, acl_epoch: int
    ) -> ZoomCredential:
        stored = self._load_credential(credential_id)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        updated = self._clone_credential(stored, status=CredentialStatus.EXPIRED)
        written = self._put_credential(updated)
        self._audit(principal, acl_epoch, "zoom.credential_expire", written.id, "expired")
        return written

    def revoke_credential(
        self, credential_id: str, *, principal: Principal, acl_epoch: int
    ) -> ZoomCredential:
        stored = self._load_credential(credential_id)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        updated = self._clone_credential(stored, status=CredentialStatus.REVOKED)
        written = self._put_credential(updated)
        self._audit(principal, acl_epoch, "zoom.credential_revoke", written.id, "revoked")
        return written

    def prepare_import(
        self,
        *,
        project_id: str,
        branch_id: str,
        revision_id: str,
        principal: Principal,
        acl_epoch: int,
    ) -> ConsentView:
        session = self.meetings.begin_session(
            project_id=project_id,
            branch_id=branch_id,
            revision_id=revision_id,
            principal=principal,
            acl_epoch=acl_epoch,
        )
        view = self.meetings.consent_view(session.id)
        self._audit(principal, acl_epoch, "zoom.prepare_import", session.id, view.consent_state.value)
        return view

    def import_live_recording(
        self,
        credential_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> MeetingSession:
        stored = self._usable_credential(credential_id, principal, acl_epoch)
        del stored
        require_zoom_sandbox()
        raise ZoomSandboxUnavailableError(
            "Zoom live recording fetch is not completed without a live sandbox; "
            "EXT-ZOOM-SANDBOX stays NOT_RUN"
        )

    def handle_webhook(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
        credential_id: str,
        principal: Principal,
        acl_epoch: int,
    ) -> MeetingSession:
        stored = self._usable_credential(credential_id, principal, acl_epoch)
        timestamp = headers.get(TIMESTAMP_HEADER, "")
        signature = headers.get(SIGNATURE_HEADER, "")
        expected = sign_zoom_payload(self.webhook_secret, timestamp, body)
        if not timestamp or not hmac.compare_digest(signature, expected):
            raise ZoomWebhookError("Zoom webhook signature is invalid")
        if not self._timestamp_in_window(timestamp):
            raise ZoomWebhookError("Zoom webhook timestamp is outside the replay window")
        payload = json.loads(body.decode("utf-8"))
        event_id = str(payload.get("event_id") or "")
        meeting_id = str(payload.get("meeting_id") or "")
        if not event_id or not meeting_id:
            raise ZoomWebhookError("Zoom webhook requires event_id and meeting_id")
        if self._seen(event_id):
            raise ZoomWebhookError(f"duplicate Zoom webhook event {event_id}")
        view = self.meetings.consent_view(meeting_id)
        if view.consent_state is not ConsentState.GRANTED:
            raise ZoomWebhookError("Zoom import requires visible granted recording consent")
        utterances = tuple(
            Utterance(
                id=f"utt_{new_ulid()}",
                speaker_label=str(item.get("speaker_label") or "unknown"),
                start_ms=int(item.get("start_ms") or 0),
                end_ms=int(item.get("end_ms") or 0),
                text=str(item.get("text") or ""),
            )
            for item in payload.get("utterances", ())
        )
        imported = self.meetings.import_transcript(
            meeting_id,
            utterances=utterances,
            principal=principal,
            acl_epoch=acl_epoch,
        )
        self._remember_event(event_id)
        self._audit(principal, acl_epoch, "zoom.webhook_import", meeting_id, stored.id)
        return imported

    def _usable_credential(
        self, credential_id: str, principal: Principal, acl_epoch: int
    ) -> ZoomCredential:
        stored = self._load_credential(credential_id)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        if stored.status is CredentialStatus.REVOKED:
            raise ZoomTokenError("revoked Zoom credential cannot import recordings")
        if stored.status is CredentialStatus.EXPIRED or self._expired(stored):
            raise ZoomTokenError("expired Zoom credential cannot import recordings")
        return stored

    def _expired(self, stored: ZoomCredential) -> bool:
        return stored.expires_at <= self.clock()

    def _timestamp_in_window(self, timestamp: str) -> bool:
        try:
            event_unix = int(timestamp)
        except ValueError:
            return False
        now = datetime.fromisoformat(self.clock().replace("Z", "+00:00")).astimezone(UTC)
        return abs(int(now.timestamp()) - event_unix) <= REPLAY_WINDOW_SECONDS

    def _seen(self, event_id: str) -> bool:
        return event_id in load_index(self.workspace).get("seen_event_ids", [])

    def _remember_event(self, event_id: str) -> None:
        def persist(index: dict[str, Any]) -> None:
            seen = list(index.get("seen_event_ids", []))
            if event_id not in seen:
                seen.append(event_id)
            index["seen_event_ids"] = seen

        mutate_index(self.workspace, persist)

    def _load_credential(self, credential_id: str) -> ZoomCredential:
        index = load_index(self.workspace)
        digest = dict(index.get("credential_digests", {})).get(credential_id)
        if digest is None:
            raise ZoomTokenError(f"Zoom credential {credential_id} is not in the index")
        return ZoomCredential.from_dict(load_payload(self.workspace, str(digest)))

    def _put_credential(self, stored: ZoomCredential) -> ZoomCredential:
        def persist(index: dict[str, Any]) -> ZoomCredential:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("credential_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["credential_ids"] = ids
            digests = dict(index.get("credential_digests", {}))
            digests[stored.id] = digest
            index["credential_digests"] = digests
            return stored

        return mutate_index(self.workspace, persist)

    @staticmethod
    def _clone_credential(
        stored: ZoomCredential, *, status: CredentialStatus
    ) -> ZoomCredential:
        return ZoomCredential(
            id=stored.id,
            project_id=stored.project_id,
            actor_id=stored.actor_id,
            scopes=stored.scopes,
            status=status,
            expires_at=stored.expires_at,
            token_digest=stored.token_digest,
            created_at=stored.created_at,
        )

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )

    def _audit(
        self,
        principal: Principal,
        acl_epoch: int,
        operation: str,
        object_id: str,
        reason: str,
    ) -> None:
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=operation,
            object_kind="zoom_adapter",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
