"""HMAC-signed, replay-protected, locally recorded webhooks."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.identity.api import Principal
from movie_muse.persistence.api import LocalWorkspace, digest_payload, utc_now
from movie_muse.schemas.api import new_ulid
from movie_muse.webhooks.errors import WebhookReplayError, WebhookSignatureError
from movie_muse.webhooks.index import load_index, mutate_index, put_payload
from movie_muse.webhooks.types import (
    REPLAY_WINDOW_SECONDS,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    WebhookDelivery,
)


def sign_webhook(signing_key: str, timestamp: str, body: bytes) -> str:
    mac = hmac.new(
        signing_key.encode(),
        f"{timestamp}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()
    return f"v0={mac}"


class WebhookService:
    """Inbound verify and outbound local delivery. network_sent stays False."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        *,
        signing_key: str,
        clock: Callable[[], datetime] | None = None,
        replay_window_seconds: int = REPLAY_WINDOW_SECONDS,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.signing_key = signing_key
        self.clock = clock or (lambda: datetime.now(UTC))
        self.replay_window_seconds = replay_window_seconds

    def emit(
        self,
        project_id: str,
        *,
        event_type: str,
        payload: Mapping[str, object],
        principal: Principal,
        acl_epoch: int,
    ) -> WebhookDelivery:
        self.authorization.require(
            principal,
            Action.EXPORT,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )
        event_id = f"whe_{new_ulid()}"
        body = json.dumps(
            {"event_id": event_id, "event_type": event_type, "payload": dict(payload)},
            sort_keys=True,
        ).encode()
        timestamp = str(int(self.clock().timestamp()))
        signature = sign_webhook(self.signing_key, timestamp, body)
        delivery = WebhookDelivery(
            id=f"whk_{new_ulid()}",
            event_id=event_id,
            event_type=event_type,
            payload_digest=digest_payload(dict(payload))[1],
            signature=signature,
            network_sent=False,
            created_at=utc_now(),
        )
        written = self._put(delivery)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="webhook.emit",
            object_kind="webhook",
            object_id=written.id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=event_type,
        )
        return written

    def ingest(
        self,
        project_id: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        principal: Principal,
        acl_epoch: int,
    ) -> WebhookDelivery:
        self.authorization.require(
            principal,
            Action.PROPOSE,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )
        timestamp = headers.get(TIMESTAMP_HEADER, "")
        signature = headers.get(SIGNATURE_HEADER, "")
        expected = sign_webhook(self.signing_key, timestamp, body)
        if not timestamp or not hmac.compare_digest(signature, expected):
            raise WebhookSignatureError("webhook signature is invalid")
        if not self._timestamp_in_window(timestamp):
            raise WebhookSignatureError("webhook timestamp is outside the replay window")
        payload = json.loads(body.decode("utf-8"))
        event_id = str(payload.get("event_id") or "")
        event_type = str(payload.get("event_type") or "")
        if not event_id or not event_type:
            raise WebhookSignatureError("webhook requires event_id and event_type")
        if self._seen(event_id):
            raise WebhookReplayError(f"duplicate webhook event {event_id}")
        inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
        delivery = WebhookDelivery(
            id=f"whk_{new_ulid()}",
            event_id=event_id,
            event_type=event_type,
            payload_digest=digest_payload(dict(inner))[1],
            signature=signature,
            network_sent=False,
            created_at=utc_now(),
        )
        written = self._put(delivery)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="webhook.ingest",
            object_kind="webhook",
            object_id=written.id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=event_id,
        )
        return written

    def _timestamp_in_window(self, timestamp: str) -> bool:
        try:
            value = int(timestamp)
        except ValueError:
            return False
        now = int(self.clock().timestamp())
        return abs(now - value) <= self.replay_window_seconds

    def _seen(self, event_id: str) -> bool:
        index = load_index(self.workspace)
        return event_id in list(index.get("event_ids", []))

    def _put(self, stored: WebhookDelivery) -> WebhookDelivery:
        def persist(index: dict[str, Any]) -> WebhookDelivery:
            digest = put_payload(self.workspace, stored.to_dict())
            events = list(index.get("event_ids", []))
            if stored.event_id not in events:
                events.append(stored.event_id)
            index["event_ids"] = events
            ids = list(index.get("delivery_ids", []))
            ids.append(stored.id)
            index["delivery_ids"] = ids
            digests = dict(index.get("delivery_digests", {}))
            digests[stored.id] = digest
            index["delivery_digests"] = digests
            return stored

        return mutate_index(self.workspace, persist)
