"""Signed webhook envelopes and local delivery records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SIGNATURE_HEADER = "X-Movie-Muse-Signature"
TIMESTAMP_HEADER = "X-Movie-Muse-Timestamp"
REPLAY_WINDOW_SECONDS = 300


@dataclass(frozen=True, slots=True)
class WebhookDelivery:
    id: str
    event_id: str
    event_type: str
    payload_digest: str
    signature: str
    network_sent: bool
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload_digest": self.payload_digest,
            "signature": self.signature,
            "network_sent": self.network_sent,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WebhookDelivery:
        return cls(
            id=str(data["id"]),
            event_id=str(data["event_id"]),
            event_type=str(data["event_type"]),
            payload_digest=str(data["payload_digest"]),
            signature=str(data["signature"]),
            network_sent=bool(data.get("network_sent", False)),
            created_at=str(data["created_at"]),
        )
