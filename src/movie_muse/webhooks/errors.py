"""Typed failures for signed mesh webhooks."""

from __future__ import annotations


class WebhookError(RuntimeError):
    """Base class for webhook failures."""


class WebhookSignatureError(WebhookError):
    """HMAC signature or replay window failed."""


class WebhookReplayError(WebhookError):
    """Duplicate event_id; deliveries are idempotent."""
