"""Public surface of ``movie_muse.webhooks``.

Hosts must import this module, never sibling internals.
Deliveries are HMAC-signed, idempotent, and locally recorded.
"""

from __future__ import annotations

from movie_muse.webhooks.errors import WebhookError, WebhookReplayError, WebhookSignatureError
from movie_muse.webhooks.service import WebhookService, sign_webhook
from movie_muse.webhooks.types import (
    REPLAY_WINDOW_SECONDS,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    WebhookDelivery,
)

__all__ = [
    "REPLAY_WINDOW_SECONDS",
    "SIGNATURE_HEADER",
    "TIMESTAMP_HEADER",
    "WebhookDelivery",
    "WebhookError",
    "WebhookReplayError",
    "WebhookService",
    "WebhookSignatureError",
    "sign_webhook",
]
