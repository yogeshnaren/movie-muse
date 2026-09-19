"""Signed, replay-protected webhooks stay local."""

from __future__ import annotations

import json

import pytest

from movie_muse.webhooks.api import (
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    WebhookReplayError,
    WebhookSignatureError,
    sign_webhook,
)


def test_emit_is_signed_and_not_network_sent(mesh_stack) -> None:
    delivery = mesh_stack.webhooks.emit(
        mesh_stack.project.id,
        event_type="proposal.submitted",
        payload={"proposal_id": "prp_example"},
        principal=mesh_stack.principal,
        acl_epoch=mesh_stack.epoch,
    )
    assert delivery.network_sent is False
    assert delivery.signature.startswith("v0=")
    assert delivery.event_id.startswith("whe_")


def test_ingest_requires_valid_signature_and_rejects_replay(mesh_stack) -> None:
    event_id = "whe_unique_event"
    payload = {"event_id": event_id, "event_type": "artifact.approved", "payload": {"ok": True}}
    body = json.dumps(payload, sort_keys=True).encode()
    timestamp = str(int(mesh_stack.clock().timestamp()))
    signature = sign_webhook("mesh-hmac", timestamp, body)
    headers = {SIGNATURE_HEADER: signature, TIMESTAMP_HEADER: timestamp}
    first = mesh_stack.webhooks.ingest(
        mesh_stack.project.id,
        headers=headers,
        body=body,
        principal=mesh_stack.principal,
        acl_epoch=mesh_stack.epoch,
    )
    assert first.network_sent is False
    with pytest.raises(WebhookReplayError):
        mesh_stack.webhooks.ingest(
            mesh_stack.project.id,
            headers=headers,
            body=body,
            principal=mesh_stack.principal,
            acl_epoch=mesh_stack.epoch,
        )
    with pytest.raises(WebhookSignatureError):
        mesh_stack.webhooks.ingest(
            mesh_stack.project.id,
            headers={SIGNATURE_HEADER: "v0=deadbeef", TIMESTAMP_HEADER: timestamp},
            body=body,
            principal=mesh_stack.principal,
            acl_epoch=mesh_stack.epoch,
        )
